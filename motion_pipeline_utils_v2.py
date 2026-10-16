"""
motion_pipeline_utils_v2.py

Utilities for:
1) building send dataframe from a WAV file
2) playing WAV and sending prepared motion to Unity in sync

This file keeps the same role and logic as close as possible to
Motion_Generation_and_Send_to_Unity_v1.py, but splits the functionality
so it can be reused inside the new multi-thread runtime.

Main differences from the original standalone runtime:
- build_send_dataframe_from_wav(...) only builds motion dataframe
- send_prebuilt_motion_in_sync(...) only plays audio + sends prepared motion
- Unity TCP connection is passed in from outside
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import sounddevice as sd
import soundfile as sf

from motion_inference_v3_cpu import predict_one_wav_without_excel, ensure_dir, strip_ext
from head_angle_from_motion_v3 import add_roll_yaw_to_motion_df, HeadAngleConfig
from lip_dist_from_motion_v1 import add_lip_dist_to_motion_df, LipDistConfig
from unity_tcp_sender_v7 import UnityTcpServer


# ============================================================
# PLAYBACK FIX CONFIG
# ============================================================
TAIL_PAD_MS = 200


# ============================================================
# CONFIG
# ============================================================
@dataclass
class MotionRuntimeConfig:
    # transformer model
    model_dir: str = r"D:\Virtual officer\outputs_transformer_local_window"

    # lip MLP model
    lip_mlp_model_dir: str = r"D:\Virtual officer\outputs_lip_mlp_local_window"

    # saved outputs
    save_dir: str = r"./runtime_outputs"

    # output motion step used by inference
    output_time_step_sec: float = 0.04
    max_output_steps: Optional[int] = None

    # TCP server for Unity
    host: str = "127.0.0.1"
    port: int = 5005

    # progress-based speed correction
    progress_gain: float = 0.35
    dt_min_ratio: float = 0.35
    dt_max_ratio: float = 2.20

    # loop sleep granularity
    idle_sleep_sec: float = 0.001

    # final sync tolerance
    force_catchup_if_progress_error_gt: float = 0.04

    # log
    print_every_n_sent: int = 20

    # keep generated sentence motion csv
    save_sentence_motion_csv: bool = True

    # angle config
    angle_cfg: HeadAngleConfig = field(
        default_factory=lambda: HeadAngleConfig(
            roll_min_deg=-5.0,
            roll_max_deg=5.0,
            yaw_min_deg=-5.0,
            yaw_max_deg=3.0,
            roll_angle_range_deg=10.0,
            yaw_angle_range_deg=30.0,
            roll_sign=1.0,
            yaw_sign=1.0,
            roll_offset_deg=0.0,
            yaw_offset_deg=0.0,
            smooth_alpha=0.25,
            use_fade_envelope=True,
            fade_ratio=0.10,
            min_fade_frames=5,
            max_fade_frames=30,
        )
    )

    # lip config
    lip_cfg: LipDistConfig = field(
        default_factory=lambda: LipDistConfig(
            lip_open_col="lip_open_dist_3d",
            mouth_width_col="mouth_width_dist_3d",
            upper_lip_col="upper_lip_thickness_3d",
            lower_lip_col="lower_lip_thickness_3d",
            lip_open_sign=1.0,
            mouth_width_sign=1.0,
            upper_lip_sign=1.0,
            lower_lip_sign=1.0,
            lip_open_offset=0.0,
            mouth_width_offset=0.0,
            upper_lip_offset=0.0,
            lower_lip_offset=0.0,
            smooth_alpha=0.25,
            use_fade_envelope=True,
            fade_ratio=0.10,
            min_fade_frames=5,
            max_fade_frames=30,
        )
    )


# ============================================================
# VALIDATION / AUDIO HELPERS
# ============================================================
def validate_motion_config(cfg: MotionRuntimeConfig) -> None:
    """
    Validate model paths and prepare output directory.
    """
    ensure_dir(cfg.save_dir)

    if not os.path.isdir(cfg.model_dir):
        raise FileNotFoundError(f"Transformer model directory not found: {cfg.model_dir}")
    if not os.path.isdir(cfg.lip_mlp_model_dir):
        raise FileNotFoundError(f"Lip MLP model directory not found: {cfg.lip_mlp_model_dir}")


def get_wav_duration_sec(path: Union[str, Path]) -> float:
    """
    Return WAV duration in seconds.
    """
    info = sf.info(str(path))
    if info.samplerate <= 0:
        raise RuntimeError(f"Invalid samplerate for file: {path}")
    return float(info.frames) / float(info.samplerate)


def load_wav_for_playback(path: Union[str, Path], tail_pad_ms: int = TAIL_PAD_MS) -> tuple[np.ndarray, int]:
    """
    Load WAV as float32 and append tail silence to reduce truncation risk.
    Returns:
        data : np.ndarray, shape (N, C)
        sr   : int
    """
    data, sr = sf.read(str(path), dtype="float32")

    if data.ndim == 1:
        data = data[:, None]

    pad_len = int(sr * (tail_pad_ms / 1000.0))
    if pad_len > 0:
        pad = np.zeros((pad_len, data.shape[1]), dtype=np.float32)
        data = np.vstack([data, pad])

    return data, sr


# ============================================================
# BUILD MOTION DATAFRAME
# ============================================================
def build_send_dataframe_from_wav(
    wav_path: Union[str, Path],
    cfg: MotionRuntimeConfig,
    save_dir: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Build the dataframe that will be sent to Unity.

    Steps:
    1) Predict motion from WAV
    2) Add roll / yaw
    3) Add / overwrite 4 lip channels in [0, 1]

    Returns
    -------
    pd.DataFrame
        Dataframe containing:
        - time_sec
        - roll
        - yaw
        - lip_open_dist_3d
        - mouth_width_dist_3d
        - upper_lip_thickness_3d
        - lower_lip_thickness_3d
        plus any original motion columns.
    """
    wav_path = str(wav_path)

    df_motion = predict_one_wav_without_excel(
        wav_path=wav_path,
        model_dir=cfg.model_dir,
        lip_mlp_model_dir=cfg.lip_mlp_model_dir,
        output_time_step_sec=cfg.output_time_step_sec,
        max_output_steps=cfg.max_output_steps,
        save_csv_path=None,
        verbose=True,
    )

    # Add roll / yaw
    df_send = add_roll_yaw_to_motion_df(df_motion, cfg=cfg.angle_cfg)

    # Add / overwrite 4 lip channels in [0, 1]
    df_send = add_lip_dist_to_motion_df(df_send, cfg=cfg.lip_cfg)

    if save_dir is not None:
        ensure_dir(str(save_dir))
        base = strip_ext(wav_path)

        motion_csv = os.path.join(str(save_dir), f"{base}_motion_pred.csv")
        send_csv = os.path.join(str(save_dir), f"{base}_motion_with_head_and_lip.csv")

        df_motion.to_csv(motion_csv, index=False, encoding="utf-8-sig")
        df_send.to_csv(send_csv, index=False, encoding="utf-8-sig")

        print(f"[INFO] Saved motion CSV    : {motion_csv}")
        print(f"[INFO] Saved head+lip CSV : {send_csv}")

    return df_send


# ============================================================
# SEND PREBUILT MOTION IN SYNC
# ============================================================
def send_prebuilt_motion_in_sync(
    df_send: pd.DataFrame,
    wav_path: Union[str, Path],
    tcp: UnityTcpServer,
    cfg: MotionRuntimeConfig,
) -> None:
    """
    Play WAV and send prepared motion to Unity in sync.

    Parameters
    ----------
    df_send : pd.DataFrame
        Prepared dataframe containing head/lip values to send.
    wav_path : str or Path
        WAV file path corresponding to df_send.
    tcp : UnityTcpServer
        An already-connected UnityTcpServer instance.
    cfg : MotionRuntimeConfig
        Runtime sync configuration.
    """
    required_cols = [
        "time_sec",
        "roll",
        "yaw",
        "lip_open_dist_3d",
        "mouth_width_dist_3d",
        "upper_lip_thickness_3d",
        "lower_lip_thickness_3d",
    ]
    for c in required_cols:
        if c not in df_send.columns:
            raise KeyError(f"df_send must contain '{c}' column.")

    wav_path = Path(wav_path)
    audio_duration = get_wav_duration_sec(wav_path)

    total_frames = len(df_send)
    if total_frames <= 0:
        raise RuntimeError("No motion frames to send.")

    base_dt = audio_duration / float(total_frames)
    dt_min = base_dt * cfg.dt_min_ratio
    dt_max = base_dt * cfg.dt_max_ratio

    print("=" * 80)
    print("[RUNTIME] Audio-motion sync sender")
    print(f"[RUNTIME] WAV file          : {wav_path}")
    print(f"[RUNTIME] WAV duration      : {audio_duration:.6f} s")
    print(f"[RUNTIME] Motion frames     : {total_frames}")
    print(f"[RUNTIME] Base dt           : {base_dt:.6f} s")
    print(f"[RUNTIME] dt min / dt max   : {dt_min:.6f} / {dt_max:.6f} s")
    print("=" * 80)

    data, sr = load_wav_for_playback(wav_path, tail_pad_ms=TAIL_PAD_MS)

    print("[RUNTIME] Starting audio playback ...")
    sd.play(data, sr)
    t0 = time.perf_counter()
    print(f"[RUNTIME] Audio started at t0={t0:.6f}")

    send_index = 0
    next_send_time = t0

    while send_index < total_frames:
        now = time.perf_counter()
        elapsed = now - t0

        audio_progress = np.clip(elapsed / max(audio_duration, 1e-8), 0.0, 1.0)
        motion_progress = send_index / float(total_frames)

        progress_error = float(audio_progress - motion_progress)

        # If motion is too slow compared to audio, catch up aggressively
        if progress_error > cfg.force_catchup_if_progress_error_gt:
            next_send_time = min(next_send_time, now)

        if now >= next_send_time:
            row = df_send.iloc[send_index]

            roll = float(row["roll"])
            yaw = float(row["yaw"])
            lip_open_dist_3d = float(row["lip_open_dist_3d"])
            mouth_width_dist_3d = float(row["mouth_width_dist_3d"])
            upper_lip_thickness_3d = float(row["upper_lip_thickness_3d"])
            lower_lip_thickness_3d = float(row["lower_lip_thickness_3d"])

            tcp.send_face_data(
                roll=roll,
                yaw=yaw,
                lip_open_dist_3d=lip_open_dist_3d,
                mouth_width_dist_3d=mouth_width_dist_3d,
                upper_lip_thickness_3d=upper_lip_thickness_3d,
                lower_lip_thickness_3d=lower_lip_thickness_3d,
            )

            print(
                f"[SEND] idx={send_index:04d}/{total_frames - 1:04d} | "
                f"roll={roll:+8.3f} | yaw={yaw:+8.3f} | "
                f"lip_open={lip_open_dist_3d:6.3f} | "
                f"mouth_width={mouth_width_dist_3d:6.3f} | "
                f"upper_lip={upper_lip_thickness_3d:6.3f} | "
                f"lower_lip={lower_lip_thickness_3d:6.3f}"
            )

            send_index += 1

            # Progress-based dt correction
            corrected_dt = base_dt * (1.0 - cfg.progress_gain * progress_error)
            corrected_dt = float(np.clip(corrected_dt, dt_min, dt_max))

            next_send_time = now + corrected_dt

            if (send_index % cfg.print_every_n_sent == 0) or (send_index == total_frames):
                print(
                    f"[RUNTIME] sent {send_index}/{total_frames} | "
                    f"audio_prog={audio_progress:.4f} | "
                    f"motion_prog={motion_progress:.4f} | "
                    f"err={progress_error:+.4f} | "
                    f"dt={corrected_dt:.4f}"
                )
        else:
            time.sleep(cfg.idle_sleep_sec)

    # Wait briefly for audio playback to finish
    sd.wait()
    print("[RUNTIME] Audio finished and all motion frames sent.")


# ============================================================
# OPTIONAL STANDALONE TEST
# ============================================================
def main() -> None:
    """
    Standalone test entry.
    This keeps usage close to the original standalone motion runtime.
    """
    cfg = MotionRuntimeConfig(
        model_dir=r"D:\Virtual officer\outputs_transformer_local_window",
        lip_mlp_model_dir=r"D:\Virtual officer\outputs_lip_mlp_local_window",
        save_dir=r"./runtime_outputs",
        output_time_step_sec=0.04,
        max_output_steps=None,
        host="127.0.0.1",
        port=5005,
        progress_gain=0.35,
        dt_min_ratio=0.35,
        dt_max_ratio=2.20,
        idle_sleep_sec=0.001,
        force_catchup_if_progress_error_gt=0.04,
        print_every_n_sent=20,
        angle_cfg=HeadAngleConfig(
            roll_min_deg=-5.0,
            roll_max_deg=5.0,
            yaw_min_deg=-5.0,
            yaw_max_deg=5.0,
            roll_angle_range_deg=10.0,
            yaw_angle_range_deg=30.0,
            roll_sign=1.0,
            yaw_sign=1.0,
            roll_offset_deg=0.0,
            yaw_offset_deg=0.0,
            smooth_alpha=0.25,
            use_fade_envelope=True,
            fade_ratio=0.10,
            min_fade_frames=5,
            max_fade_frames=30,
        ),
        lip_cfg=LipDistConfig(
            lip_open_col="lip_open_dist_3d",
            mouth_width_col="mouth_width_dist_3d",
            upper_lip_col="upper_lip_thickness_3d",
            lower_lip_col="lower_lip_thickness_3d",
            lip_open_sign=1.0,
            mouth_width_sign=1.0,
            upper_lip_sign=1.0,
            lower_lip_sign=1.0,
            lip_open_offset=0.0,
            mouth_width_offset=0.0,
            upper_lip_offset=0.0,
            lower_lip_offset=0.0,
            smooth_alpha=0.25,
            use_fade_envelope=True,
            fade_ratio=0.10,
            min_fade_frames=5,
            max_fade_frames=30,
        ),
    )

    wav_path = r"D:/Virtual officer/out_audio/out_20260302_170003_sent_001.wav"

    validate_motion_config(cfg)

    if not os.path.isfile(wav_path):
        raise FileNotFoundError(f"WAV path not found: {wav_path}")

    print("=" * 80)
    print("MOTION PIPELINE UTILS V2 - STANDALONE TEST")
    print("=" * 80)

    df_send = build_send_dataframe_from_wav(
        wav_path=wav_path,
        cfg=cfg,
        save_dir=cfg.save_dir if cfg.save_sentence_motion_csv else None,
    )

    tcp = UnityTcpServer(host=cfg.host, port=cfg.port)

    try:
        tcp.start_and_wait_for_client()
        send_prebuilt_motion_in_sync(
            df_send=df_send,
            wav_path=wav_path,
            tcp=tcp,
            cfg=cfg,
        )
    finally:
        try:
            sd.stop()
        except Exception:
            pass
        tcp.close()

    print("[DONE]")


if __name__ == "__main__":
    main()


"""
Abbreviations:
- TCP: Transmission Control Protocol, giao thức truyền tải tin cậy.
- WAV: Waveform Audio File Format, định dạng tệp âm thanh WAV.
- CSV: Comma-Separated Values, định dạng tệp bảng dữ liệu.
- MLP: Multi-Layer Perceptron, mạng nơ-ron truyền thẳng nhiều lớp.
- ms: millisecond, mili giây.
"""