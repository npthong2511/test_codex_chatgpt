# volume_trigger_recorder.py
# ============================================================
# Realtime microphone volume-triggered recorder
#
# Purpose:
# - Continuously read microphone frames.
# - Estimate neutral/background volume in dBFS.
# - Start recording when volume rises above neutral + start margin.
# - Stop recording when volume returns near neutral for a configured duration.
#
# This file contains the calculation and recording logic used by
# voice_motion_runtime_v7.py.
# ============================================================

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


@dataclass
class VolumeTriggerConfig:
    """
    Configuration for RMS/dBFS-based automatic recording.
    """

    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "float32"

    # Size of each microphone frame used for realtime volume checking.
    mic_frame_ms: int = 30

    # Initial duration used to measure neutral/background microphone volume.
    # In v7 this is called only once when the runtime starts.
    mic_neutral_calibration_sec: float = 2.0

    # Start/stop thresholds are computed relative to neutral_dbfs.
    start_margin_db: float = 12.0
    stop_margin_db: float = 6.0

    # Require volume to stay above start threshold for this long before starting.
    start_required_sec: float = 0.12

    # Stop only after volume has stayed below stop threshold for this long.
    silence_stop_sec: float = 0.8

    # Keep a short amount of audio before the trigger to avoid losing first words.
    pre_roll_sec: float = 0.3

    # Add a short extra tail after stop condition is met.
    post_roll_sec: float = 0.2

    # Reject recordings shorter than this.
    min_record_sec: float = 0.5

    # Safety cap to prevent infinite recording.
    max_record_sec: float = 15.0

    # Numerical stability for dBFS calculation.
    eps: float = 1e-8


@dataclass
class VolumeTriggeredRecordResult:
    saved: bool
    wav_path: Path
    duration_sec: float
    neutral_dbfs: float
    start_threshold_dbfs: float
    stop_threshold_dbfs: float
    reason: str


def frame_rms(frame: np.ndarray) -> float:
    """
    Calculate RMS amplitude from a float audio frame.
    """
    if frame.size == 0:
        return 0.0
    x = frame.astype(np.float32, copy=False)
    return float(np.sqrt(np.mean(np.square(x))))


def rms_to_dbfs(rms: float, eps: float = 1e-8) -> float:
    """
    Convert RMS amplitude to dBFS.
    For float audio, 1.0 is treated as full-scale.
    """
    return float(20.0 * np.log10(max(float(rms), float(eps))))


def frame_dbfs(frame: np.ndarray, eps: float = 1e-8) -> float:
    """
    Calculate dBFS directly from an audio frame.
    """
    return rms_to_dbfs(frame_rms(frame), eps=eps)


def _frame_samples(cfg: VolumeTriggerConfig) -> int:
    return max(1, int(cfg.sample_rate * cfg.mic_frame_ms / 1000.0))


def _stop_requested(stop_event: Optional[object]) -> bool:
    if stop_event is None:
        return False
    try:
        return bool(stop_event.is_set())
    except Exception:
        return False


def _read_stream_frame(stream: sd.InputStream, frame_samples: int) -> np.ndarray:
    """
    Blocking read of one microphone frame from an existing InputStream.
    """
    frame, overflowed = stream.read(frame_samples)
    if overflowed:
        print("[AUTO-REC] Warning: input overflow.")
    return np.asarray(frame, dtype=np.float32)


def calibrate_neutral_dbfs(
    cfg: VolumeTriggerConfig,
    stop_event: Optional[object] = None,
    verbose: bool = True,
) -> float:
    """
    Measure neutral/background volume for cfg.mic_neutral_calibration_sec.
    Median dBFS is used for robustness against short noises.
    """
    frame_samples = _frame_samples(cfg)
    frame_sec = frame_samples / float(cfg.sample_rate)
    n_frames = max(1, int(round(cfg.mic_neutral_calibration_sec / frame_sec)))
    values: List[float] = []

    if verbose:
        print(
            f"[AUTO-REC] Calibrating neutral mic volume "
            f"for {cfg.mic_neutral_calibration_sec:.2f}s ..."
        )
        print("[AUTO-REC] Please stay quiet during calibration.")

    with sd.InputStream(
        samplerate=cfg.sample_rate,
        channels=cfg.channels,
        dtype=cfg.dtype,
        blocksize=frame_samples,
    ) as stream:
        for _ in range(n_frames):
            if _stop_requested(stop_event):
                break
            frame = _read_stream_frame(stream, frame_samples)
            values.append(frame_dbfs(frame, eps=cfg.eps))

    if not values:
        return -80.0

    neutral = float(np.median(np.asarray(values, dtype=np.float32)))

    if verbose:
        print(f"[AUTO-REC] neutral_dbfs={neutral:.2f} dBFS")

    return neutral


def save_float_audio_to_wav(path: Path, audio_float: np.ndarray, sample_rate: int) -> None:
    """
    Save float audio as PCM_16 WAV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    audio_float = np.asarray(audio_float, dtype=np.float32)
    if audio_float.ndim == 1:
        audio_float = audio_float.reshape(-1, 1)
    audio_float = np.clip(audio_float, -1.0, 1.0)
    audio_int16 = (audio_float * 32767.0).astype(np.int16)
    sf.write(str(path), audio_int16, sample_rate, subtype="PCM_16")


def record_wav_by_volume_trigger(
    path: Path,
    cfg: VolumeTriggerConfig,
    neutral_dbfs: Optional[float] = None,
    stop_event: Optional[object] = None,
    verbose: bool = True,
) -> VolumeTriggeredRecordResult:
    """
    Record a WAV file using simple RMS/dBFS voice activity logic.

    neutral_dbfs should normally be passed from the one-time calibration step.
    If neutral_dbfs is None, this function calibrates once before waiting.

    State logic:
    - IDLE: keep a pre-roll buffer and wait for volume > start threshold.
    - RECORDING: collect frames.
    - STOP: if volume stays below stop threshold for silence_stop_sec, stop.

    This function blocks until a recording is saved, max_record_sec is hit,
    or stop_event is set.
    """
    path = Path(path)
    frame_samples = _frame_samples(cfg)
    frame_sec = frame_samples / float(cfg.sample_rate)

    if neutral_dbfs is None:
        neutral_dbfs = calibrate_neutral_dbfs(cfg, stop_event=stop_event, verbose=verbose)

    start_threshold_dbfs = float(neutral_dbfs) + cfg.start_margin_db
    stop_threshold_dbfs = float(neutral_dbfs) + cfg.stop_margin_db

    pre_roll_frames = max(1, int(round(cfg.pre_roll_sec / frame_sec)))
    post_roll_frames = max(0, int(round(cfg.post_roll_sec / frame_sec)))
    start_required_frames = max(1, int(round(cfg.start_required_sec / frame_sec)))
    silence_stop_frames = max(1, int(round(cfg.silence_stop_sec / frame_sec)))
    max_record_frames = max(1, int(round(cfg.max_record_sec / frame_sec)))

    pre_roll: Deque[np.ndarray] = deque(maxlen=pre_roll_frames)
    recorded_frames: List[np.ndarray] = []

    is_recording = False
    loud_count = 0
    silence_count = 0
    record_frame_count = 0
    stop_reason = ""

    if verbose:
        print(
            f"[AUTO-REC] Waiting for speech | "
            f"start>{start_threshold_dbfs:.2f} dBFS, "
            f"stop<{stop_threshold_dbfs:.2f} dBFS"
        )

    with sd.InputStream(
        samplerate=cfg.sample_rate,
        channels=cfg.channels,
        dtype=cfg.dtype,
        blocksize=frame_samples,
    ) as stream:
        while True:
            if _stop_requested(stop_event):
                stop_reason = "stop_event"
                break

            frame = _read_stream_frame(stream, frame_samples)
            db = frame_dbfs(frame, eps=cfg.eps)

            if not is_recording:
                pre_roll.append(frame.copy())

                if db >= start_threshold_dbfs:
                    loud_count += 1
                else:
                    loud_count = 0

                if loud_count >= start_required_frames:
                    is_recording = True
                    silence_count = 0
                    recorded_frames = [f.copy() for f in pre_roll]
                    record_frame_count = len(recorded_frames)
                    if verbose:
                        print(f"[AUTO-REC] Speech started | dbfs={db:.2f}")

                continue

            recorded_frames.append(frame.copy())
            record_frame_count += 1

            if db <= stop_threshold_dbfs:
                silence_count += 1
            else:
                silence_count = 0

            if record_frame_count >= max_record_frames:
                stop_reason = "max_record_sec"
                if verbose:
                    print(f"[AUTO-REC] Stop by max_record_sec={cfg.max_record_sec:.2f}s")
                break

            duration_so_far = record_frame_count * frame_sec
            if duration_so_far >= cfg.min_record_sec and silence_count >= silence_stop_frames:
                stop_reason = "silence_stop_sec"
                if verbose:
                    print(
                        f"[AUTO-REC] Speech ended | "
                        f"silence={silence_count * frame_sec:.2f}s, "
                        f"duration={duration_so_far:.2f}s"
                    )
                break

        if is_recording and post_roll_frames > 0 and stop_reason == "silence_stop_sec":
            for _ in range(post_roll_frames):
                if _stop_requested(stop_event):
                    break
                recorded_frames.append(_read_stream_frame(stream, frame_samples).copy())

    if not recorded_frames:
        return VolumeTriggeredRecordResult(
            saved=False,
            wav_path=path,
            duration_sec=0.0,
            neutral_dbfs=float(neutral_dbfs),
            start_threshold_dbfs=start_threshold_dbfs,
            stop_threshold_dbfs=stop_threshold_dbfs,
            reason=stop_reason or "no_recording",
        )

    audio = np.concatenate(recorded_frames, axis=0)
    duration_sec = float(audio.shape[0]) / float(cfg.sample_rate)

    if duration_sec < cfg.min_record_sec:
        return VolumeTriggeredRecordResult(
            saved=False,
            wav_path=path,
            duration_sec=duration_sec,
            neutral_dbfs=float(neutral_dbfs),
            start_threshold_dbfs=start_threshold_dbfs,
            stop_threshold_dbfs=stop_threshold_dbfs,
            reason="too_short",
        )

    save_float_audio_to_wav(path, audio, cfg.sample_rate)

    if verbose:
        print(f"[AUTO-REC] Saved input: {path} | duration={duration_sec:.2f}s")

    return VolumeTriggeredRecordResult(
        saved=True,
        wav_path=path,
        duration_sec=duration_sec,
        neutral_dbfs=float(neutral_dbfs),
        start_threshold_dbfs=start_threshold_dbfs,
        stop_threshold_dbfs=stop_threshold_dbfs,
        reason=stop_reason or "saved",
    )
