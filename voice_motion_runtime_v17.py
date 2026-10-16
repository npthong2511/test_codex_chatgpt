# V17.0 voice shell: microphone/TTS/motion inherited unchanged; dialogue uses agent17.
# Hardware integration is syntax-checked only in this offline release.
# See README_V17.md for required existing hardware modules and assets.
# voice_motion_runtime_v14_1_lite_exe.py
# ============================================================
# Voice + Motion Runtime V14.1 Lite + Local Hybrid RAG
#
# V14.1 change scope:
# - Start "Virtual_Officer_v1.exe - Shortcut" from the application directory
# - Load the system prompt from system_prompt.txt in the application directory
# - Use the curated local V14.1 RAG index (27 procedures, intent-aware retrieval)
# - Reject out-of-scope and clarify ambiguous administrative questions
# - All unrelated STT, TTS, motion, Unity, session, microphone, RAG,
#   playback, API-key failover, and threading logic are kept unchanged
#
# Pipeline:
# 1) Realtime microphone volume trigger records user speech
# 2) STT with OpenAI
# 3) LLM streaming response
# 4) Split streamed text into sentences
# 5) Thread 1: generate WAV sentence-by-sentence via ElevenLabs TTS
# 6) Thread 2: build motion dataframe from each generated WAV
# 7) Thread 3: send speech text to Unity, then play WAV and send prepared motion in sync
# 8) Thread 4: run person presence detection continuously and send result to Unity
#
# Session behavior:
# - Keep one conversation memory per detected person session
# - Activation requires valid Face + Pose for the configured consecutive hits
# - An active session is retained while either Face or Pose remains valid
# - Deactivation requires both Face and Pose to be invalid for the configured misses
# - Each turn saves text/audio/motion/artifacts into its own folder for later analysis
# ============================================================

from __future__ import annotations

# Early opt-in gate, before microphone/model/credential imports.
import json as _gate_json
from pathlib import Path as _GatePath
import sys as _gate_sys
_gate_dir = _GatePath(_gate_sys.executable).resolve().parent if getattr(_gate_sys, "frozen", False) else _GatePath(__file__).resolve().parent
if not _gate_json.loads((_gate_dir / "config.json").read_text(encoding="utf-8")).get("enable_live_api", False):
    raise SystemExit("V17 live runtime disabled. Run python -m unittest discover -s tests; enable config.json for live use.")

import copy
import json
import math
import os
import queue
import random
import shutil
import re
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import sys
import unicodedata

import mediapipe as mp
import cv2
import numpy as np
import pandas as pd
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from motion_pipeline_utils_v3 import (
    MotionRuntimeConfig,
    validate_motion_config,
    build_send_dataframe_from_wav,
    send_prebuilt_motion_in_sync,
    load_wav_for_playback,
)
from unity_tcp_sender_v7 import UnityTcpServer

from agent17.runtime import Sources as KnowledgeBase
from agent17.voice_bridge_v3 import VoiceBridge, acknowledge_playback, publish_information_on_playback
from agent17.playback import play_response_audio

from volume_trigger_recorder import (
    VolumeTriggerConfig,
    calibrate_neutral_dbfs,
    record_wav_by_volume_trigger,
)

def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()

# Explicit opt-in before reading configured credentials or launching the live runtime.
V17_CONFIG = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))
if __name__ == "__main__" and not V17_CONFIG.get("enable_live_api", False):
    raise SystemExit("V17 live API disabled. Run offline tests first; enable config.json after review.")

TRANSFORMER_MODEL_DIR = (
    APP_DIR / "models" / "outputs_transformer_local_window"
)

LIP_MLP_MODEL_DIR = (
    APP_DIR / "models" / "outputs_lip_mlp_local_window"
)

RUNTIME_OUTPUT_DIR = APP_DIR / "runtime_outputs"
OUT_DIR = APP_DIR / "out_audio"

# ============================================================
# API KEYS - V11.3 LITE
# ============================================================
# Put these two TXT files beside the .py file, or beside the .exe after build.
# File format: one key per line. Blank lines and lines beginning with # are ignored.
OPENAI_KEYS_FILE = APP_DIR / "openai_keys.txt"
ELEVENLABS_KEYS_FILE = APP_DIR / "elevenlabs_keys.txt"
SYSTEM_PROMPT_FILE = APP_DIR / "system_prompt.txt"
VIRTUAL_OFFICER_SHORTCUT_NAME = "Virtual_Officer_v1.exe - Shortcut"


def _find_virtual_officer_shortcut() -> Optional[Path]:
    """Find the requested Windows shortcut beside the running .py/.exe."""
    expected_names = {
        VIRTUAL_OFFICER_SHORTCUT_NAME.casefold(),
        f"{VIRTUAL_OFFICER_SHORTCUT_NAME}.lnk".casefold(),
    }

    try:
        for path in APP_DIR.iterdir():
            if path.is_file() and path.name.casefold() in expected_names:
                return path
    except Exception as e:
        print(
            f"[Virtual Officer] Cannot search application directory {APP_DIR}: "
            f"{type(e).__name__}: {e}"
        )

    return None


def _launch_virtual_officer_shortcut() -> None:
    """Open the Virtual Officer shortcut before waiting for its TCP connection."""
    shortcut_path = _find_virtual_officer_shortcut()
    if shortcut_path is None:
        print(
            f"[Virtual Officer] Shortcut not found in {APP_DIR}: "
            f"{VIRTUAL_OFFICER_SHORTCUT_NAME}.lnk"
        )
        return

    try:
        os.startfile(str(shortcut_path))
        print(f"[Virtual Officer] Opened: {shortcut_path.name}")
    except Exception as e:
        print(
            f"[Virtual Officer] Failed to open {shortcut_path}: "
            f"{type(e).__name__}: {e}"
        )


class AllApiKeysOutOfCreditError(RuntimeError):
    """Raised when every configured key for one provider is out of credit."""


class _StreamCreditError(RuntimeError):
    """Internal wrapper that preserves a structured streaming provider error."""

    def __init__(self, provider_error: Any):
        super().__init__("Provider reported an out-of-credit error while streaming.")
        self.provider_error = provider_error


def _load_api_keys(key_file: Path, provider_name: str) -> List[str]:
    env_name = "Open_AI" if provider_name.lower() == "openai" else "ELEVENLABS_API_KEY"
    if os.getenv(env_name):
        return [os.environ[env_name]]
    """
    Load unique API keys from a UTF-8 TXT file.

    Rules:
    - One key per line
    - Ignore blank lines
    - Ignore lines whose first non-space character is #
    """
    if not key_file.is_file():
        raise RuntimeError(
            f"Missing {provider_name} key file: {key_file}. "
            "Create it and put one API key on each line."
        )

    try:
        raw_lines = key_file.read_text(encoding="utf-8-sig").splitlines()
    except Exception as e:
        raise RuntimeError(
            f"Cannot read {provider_name} key file {key_file}: "
            f"{type(e).__name__}: {e}"
        ) from e

    keys: List[str] = []
    seen = set()
    for raw_line in raw_lines:
        key = raw_line.strip()
        if not key or key.startswith("#") or key in seen:
            continue
        keys.append(key)
        seen.add(key)

    if not keys:
        raise RuntimeError(
            f"No {provider_name} API key found in {key_file}. "
            "Put one API key on each line."
        )

    return keys


def _collect_error_fragments(error: Any) -> List[str]:
    """
    Collect only safe error fields used by OpenAI and ElevenLabs SDK errors.
    API keys and request headers are never inspected or logged.
    """
    fragments: List[str] = []
    visited = set()
    field_names = (
        "type",
        "code",
        "status",
        "status_code",
        "message",
        "detail",
        "error",
        "body",
    )

    def visit(value: Any) -> None:
        if value is None:
            return

        value_id = id(value)
        if value_id in visited:
            return
        visited.add(value_id)

        if isinstance(value, (str, int, float, bool)):
            fragments.append(str(value))
            return

        if isinstance(value, dict):
            for name in field_names:
                if name in value:
                    visit(value.get(name))
            return

        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
            return

        try:
            fragments.append(str(value))
        except Exception:
            pass

        for name in field_names:
            try:
                visit(getattr(value, name, None))
            except Exception:
                pass

    visit(error)
    return fragments


def _error_text(error: Any) -> str:
    return "\n".join(_collect_error_fragments(error)).lower()


def _is_openai_credit_error(error: Any) -> bool:
    """
    Detect OpenAI billing/quota exhaustion only.
    A normal 429 rate-limit error is intentionally not treated as no credit.
    """
    text = _error_text(error)
    markers = (
        "insufficient_quota",
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "exceeded your current quota",
    )
    return any(marker in text for marker in markers)


def _is_elevenlabs_credit_error(error: Any) -> bool:
    """
    Detect ElevenLabs credit exhaustion only.
    Rate-limit and concurrent-limit errors are intentionally not rotated.
    """
    text = _error_text(error)
    markers = (
        "quota_exceeded",
        "payment_required",
        "insufficient quota to complete the request",
        "insufficient credits",
    )
    if any(marker in text for marker in markers):
        return True

    try:
        return int(getattr(error, "status_code", 0) or 0) == 402
    except Exception:
        return False


class ApiKeyClientPool:
    """
    Thread-safe pool of lazily created, cached SDK clients.

    The selected usable client remains active. A client is skipped permanently for
    the current process only after the provider explicitly reports no credit/quota.
    """

    def __init__(
        self,
        provider_name: str,
        key_file: Path,
        client_factory: Callable[[str], Any],
    ) -> None:
        self.provider_name = provider_name
        self.key_file = key_file
        self._keys = _load_api_keys(key_file, provider_name)
        self._client_factory = client_factory
        # Match the old runtime's normal-path footprint: create only the first
        # client now, then create and cache another client only if failover occurs.
        self._clients: Dict[int, Any] = {0: client_factory(self._keys[0])}
        self._exhausted_indices = set()
        self._current_index = 0
        self._lock = threading.Lock()

        print(
            f"[API KEY] {self.provider_name}: loaded {len(self._keys)} key(s) "
            f"from {self.key_file.name}."
        )

    def candidate_indices(self) -> List[int]:
        with self._lock:
            count = len(self._keys)
            ordered_indices = [
                (self._current_index + offset) % count
                for offset in range(count)
            ]
            return [
                index
                for index in ordered_indices
                if index not in self._exhausted_indices
            ]

    def get_client(self, index: int) -> Any:
        with self._lock:
            provider_client = self._clients.get(index)
            if provider_client is None:
                provider_client = self._client_factory(self._keys[index])
                self._clients[index] = provider_client
            return provider_client

    def mark_success(self, index: int) -> None:
        with self._lock:
            if index not in self._exhausted_indices:
                self._current_index = index

    def mark_credit_exhausted(self, index: int) -> None:
        with self._lock:
            was_new = index not in self._exhausted_indices
            self._exhausted_indices.add(index)

            next_index: Optional[int] = None
            for offset in range(1, len(self._keys) + 1):
                candidate = (index + offset) % len(self._keys)
                if candidate not in self._exhausted_indices:
                    next_index = candidate
                    self._current_index = candidate
                    break

            remaining = len(self._keys) - len(self._exhausted_indices)

        if was_new:
            print(
                f"[API KEY] {self.provider_name}: key {index + 1}/{len(self._keys)} "
                f"is out of credit; remaining keys={remaining}."
            )
            if next_index is not None:
                print(
                    f"[API KEY] {self.provider_name}: switched to key "
                    f"{next_index + 1}/{len(self._keys)}."
                )

    def all_out_of_credit_error(self, operation_name: str) -> AllApiKeysOutOfCreditError:
        return AllApiKeysOutOfCreditError(
            f"{self.provider_name}: all keys in {self.key_file.name} are out of credit "
            f"while running {operation_name}."
        )


def _call_with_credit_failover(
    pool: ApiKeyClientPool,
    is_credit_error: Callable[[Any], bool],
    operation_name: str,
    operation: Callable[[Any], Any],
) -> Any:
    """Run one complete non-streaming API operation with credit-only failover."""
    last_credit_error: Optional[BaseException] = None

    for index in pool.candidate_indices():
        provider_client = pool.get_client(index)
        try:
            result = operation(provider_client)
        except Exception as e:
            if not is_credit_error(e):
                raise
            pool.mark_credit_exhausted(index)
            last_credit_error = e
            continue

        pool.mark_success(index)
        return result

    error = pool.all_out_of_credit_error(operation_name)
    if last_credit_error is not None:
        raise error from last_credit_error
    raise error


openai_client_pool = ApiKeyClientPool(
    provider_name="OpenAI",
    key_file=OPENAI_KEYS_FILE,
    client_factory=lambda key: OpenAI(api_key=key),
)

elevenlabs_client_pool = ApiKeyClientPool(
    provider_name="ElevenLabs",
    key_file=ELEVENLABS_KEYS_FILE,
    client_factory=lambda key: ElevenLabs(api_key=key),
)


# ============================================================
# MODEL CONFIG
# ============================================================
STT_MODEL = "gpt-4o-mini-transcribe"
LLM_MODEL = "gpt-5.2"

# ElevenLabs TTS
TTS_MODEL = "eleven_flash_v2_5"
TTS_VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"
TTS_LANGUAGE_CODE = "vi"
TTS_OUTPUT_FORMAT = "pcm_16000"   # convert PCM -> WAV locally
TTS_WAV_SR = 16000

# Voice style
TTS_STABILITY = 0.5
TTS_SIMILARITY_BOOST = 0.8
TTS_STYLE = 0.0
TTS_USE_SPEAKER_BOOST = True
TTS_SPEED = 1.0

# Memory / RAG helper models
SUMMARY_MODEL = "gpt-4o-mini"
FACTS_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"


# ============================================================
# RECORD CONFIG
# ============================================================
RECORD_SR = 16000
RECORD_CHANNELS = 1
RECORD_DTYPE = "float32"
DEFAULT_RECORD_SECONDS = 5.0


# ============================================================
# PLAYBACK FIX CONFIG
# ============================================================
TAIL_PAD_MS = 200
FILE_STABLE_MS = 120
FILE_CHECK_MS = 20
FILE_TIMEOUT_MS = 2500


# ============================================================
# TEXT DISPLAY CONFIG
# ============================================================
CLEAR_SPEECH_TEXT_AT_END = False


# ============================================================
# PERSON DETECTION DEFAULT CONFIG
# ============================================================
PERSON_CAMERA_INDEX = 0
PERSON_FRAME_WIDTH = 1920
PERSON_FRAME_HEIGHT = 1080

PERSON_DETECT_INTERVAL_SEC = 1.0
PERSON_REQUIRED_CONSECUTIVE_HITS = 2
PERSON_REQUIRED_CONSECUTIVE_MISSES = 3

PERSON_ROI_X_MIN_RATIO = 0.0
PERSON_ROI_X_MAX_RATIO = 1.0
PERSON_ROI_Y_MIN_RATIO = 0.0
PERSON_ROI_Y_MAX_RATIO = 1.0

PERSON_MIN_FACE_BOX_W_RATIO = 0.12
PERSON_MIN_FACE_BOX_H_RATIO = 0.12

PERSON_MIN_SHOULDER_WIDTH_RATIO = 0.10

PERSON_FACE_MIN_DET_CONF = 0.3
PERSON_POSE_MIN_DET_CONF = 0.3
PERSON_POSE_MIN_TRACK_CONF = 0.3

PERSON_VISUALIZE_DEFAULT = False
PERSON_LOOP_SLEEP_SEC = 0.01
PERSON_VERBOSE_DEFAULT = False


# ============================================================
# OUTPUT DIR
# ============================================================
OUT_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_DIR = OUT_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

KB_DIR = APP_DIR / "data"
KB_DIR.mkdir(parents=True, exist_ok=True)

PRESET_AUDIO_DIR = OUT_DIR / "preset_audios"
GREETING_AUDIOS_DIR = PRESET_AUDIO_DIR / "greeting_audios"
WAITING_AUDIOS_DIR = PRESET_AUDIO_DIR / "waiting_audios"
GREETING_AUDIOS_DIR.mkdir(parents=True, exist_ok=True)
WAITING_AUDIOS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# MEMORY CONFIG
# ============================================================
WINDOW_TURNS = 8
SUMMARY_EVERY_TURNS = 4
MAX_FACTS = 25

# Separate KB store - V12.2 hybrid metadata-aware RAG
#
# V12.2 retrieval flow:
# 1) One query embedding (same API call count as V12.1 normal path)
# 2) Canonicalize noisy legacy procedure_name values in RAM only
# 3) Global procedure scoring from clean-centroid + top clean chunks + lexical name match
# 4) Field keywords are SOFT boosts only; they never hard-lock the field
# 5) gpt-4o-mini fallback only for genuinely ambiguous top procedure candidates
# 6) Detect multiple requested intents in one citizen question
# 7) After procedure selection, retrieve matching metadata sections FIRST
# 8) Fill remaining context only from the same canonical procedure
# 9) Ask one clarification instead of mixing procedures when confidence is too low
KB_TOP_K = 5
KB_MIN_SIM = 0.22

RAG_ROUTER_MODEL = "gpt-4o-mini"
RAG_ENABLE_LLM_FALLBACK = True

RAG_ROUTE_CANDIDATE_K = 12
RAG_LLM_PROCEDURE_CANDIDATES = 5
RAG_LLM_FIELD_CANDIDATES = 5

# Objective benchmark-selected deterministic routing weights.
RAG_PROC_CENTROID_WEIGHT = 0.35
RAG_PROC_TOP_CHUNK_WEIGHT = 0.50
RAG_PROC_SECOND_CHUNK_WEIGHT = 0.15
RAG_PROC_LEXICAL_WEIGHT = 0.20
RAG_FIELD_KEYWORD_SCALE = 0.50

# Ambiguity handling. A small/close margin invokes the LLM candidate selector.
RAG_LLM_FALLBACK_MARGIN = 0.045
RAG_HARD_CLARIFY_MARGIN = 0.012
RAG_PROCEDURE_ROUTE_MIN_SCORE = 0.28
RAG_ADMIN_QUERY_MIN_SIM = 0.32

# Final evidence selection.
RAG_SECTION_SELECTED_BOOST = 0.12
RAG_NEW_SOURCE_TIE_BOOST = 0.015
RAG_PROCEDURE_SECTION_TIE_BOOST = 0.010
RAG_FINAL_CONFIDENCE_MIN = 0.30


# ============================================================
# RUNTIME CONFIG
# ============================================================
@dataclass
class VoiceMotionRuntimeConfig:
    record_seconds: float = DEFAULT_RECORD_SECONDS

    # queue size
    max_queue_size: int = 200

    # adaptive motion buffer for weaker PCs
    motion_wait_sleep_sec: float = 0.01
    initial_motion_buffer_jobs: int = 1
    max_ready_motion_jobs: int = 2
    motion_build_max_retries: int = 1

    # Keep social speech audible even if motion generation fails.
    play_audio_even_if_motion_failed: bool = True

    # send speech text packet before playing each sentence
    send_speech_text_to_unity: bool = True

    # optionally clear the displayed speech text after whole answer
    clear_speech_text_after_response: bool = CLEAR_SPEECH_TEXT_AT_END

    # verbose logs
    verbose: bool = True

    # session storage
    sessions_root_dir: Path = SESSIONS_DIR

    # person detection
    enable_person_detection: bool = True
    send_person_detection_to_unity: bool = True
    visualize_person_detection: bool = PERSON_VISUALIZE_DEFAULT
    person_detection_verbose: bool = PERSON_VERBOSE_DEFAULT

    person_camera_index: int = PERSON_CAMERA_INDEX
    person_frame_width: int = PERSON_FRAME_WIDTH
    person_frame_height: int = PERSON_FRAME_HEIGHT

    person_detect_interval_sec: float = PERSON_DETECT_INTERVAL_SEC
    person_required_consecutive_hits: int = PERSON_REQUIRED_CONSECUTIVE_HITS
    person_required_consecutive_misses: int = PERSON_REQUIRED_CONSECUTIVE_MISSES

    person_roi_x_min_ratio: float = PERSON_ROI_X_MIN_RATIO
    person_roi_x_max_ratio: float = PERSON_ROI_X_MAX_RATIO
    person_roi_y_min_ratio: float = PERSON_ROI_Y_MIN_RATIO
    person_roi_y_max_ratio: float = PERSON_ROI_Y_MAX_RATIO

    person_min_face_box_w_ratio: float = PERSON_MIN_FACE_BOX_W_RATIO
    person_min_face_box_h_ratio: float = PERSON_MIN_FACE_BOX_H_RATIO
    person_min_shoulder_width_ratio: float = PERSON_MIN_SHOULDER_WIDTH_RATIO

    person_face_min_det_conf: float = PERSON_FACE_MIN_DET_CONF
    person_pose_min_det_conf: float = PERSON_POSE_MIN_DET_CONF
    person_pose_min_track_conf: float = PERSON_POSE_MIN_TRACK_CONF

    person_loop_sleep_sec: float = PERSON_LOOP_SLEEP_SEC

    # automatic recording by realtime microphone volume
    enable_auto_recording: bool = True
    volume_trigger_cfg: VolumeTriggerConfig = field(
        default_factory=lambda: VolumeTriggerConfig(
            sample_rate=RECORD_SR,
            channels=RECORD_CHANNELS,
            dtype=RECORD_DTYPE,
            mic_frame_ms=30,
            mic_neutral_calibration_sec=2.0,
            start_margin_db=12.0,
            stop_margin_db=6.0,
            start_required_sec=0.12,
            silence_stop_sec=0.8,
            pre_roll_sec=0.3,
            post_roll_sec=0.2,
            min_record_sec=0.5,
            max_record_sec=15.0,
        )
    )

    # preset audio folders
    greeting_audios_dir: Path = GREETING_AUDIOS_DIR
    waiting_audios_dir: Path = WAITING_AUDIOS_DIR
    preset_audio_extensions: Tuple[str, ...] = (".wav", ".wave")

    # preset audio behavior
    # If a .txt file with the same stem exists, it will be sent to Unity as speech_text.
    # If no .txt exists or the text is empty, only audio + motion will be sent.
    send_preset_speech_text_to_unity: bool = False
    preset_job_id_greeting: int = -1001
    preset_job_id_waiting: int = -1002
    person_greeting_delay_sec: float = 2.0

    # Unity UI status shown only while the initial generated-response buffer waits.
    send_searching_text_to_unity: bool = False
    searching_text: str = "Đang tìm kiếm..."
    searching_text_job_id: int = -1003

    # motion config
    motion_cfg: MotionRuntimeConfig = field(
            default_factory=lambda: MotionRuntimeConfig(
            model_dir=str(TRANSFORMER_MODEL_DIR),
            lip_mlp_model_dir=str(LIP_MLP_MODEL_DIR),
            save_dir=str(RUNTIME_OUTPUT_DIR),
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
            save_sentence_motion_csv=True,
        )
    )


# ============================================================
# JOB DATA
# ============================================================
@dataclass
class AudioJob:
    job_id: int
    sentence_text: str
    wav_path: Path
    created_ts: str


@dataclass
class ResponseThreadState:
    transcript: str = ""
    full_answer: str = ""
    status: str = ""
    error: str = ""
    no_speech: bool = False
    aborted_by_person_left: bool = False
    abort_reason: str = ""


# ============================================================
# PERSON DETECTION RESULT
# ============================================================
@dataclass
class PersonDetectionState:
    person_present: bool = False
    consecutive_hits: int = 0
    consecutive_misses: int = 0
    last_face_valid: bool = False
    last_pose_valid: bool = False
    last_reason: str = "No detection yet"
    last_face_bbox: Optional[Tuple[int, int, int, int]] = None
    last_center: Optional[Tuple[int, int]] = None


# ============================================================
# SESSION / TURN DATA
# ============================================================
@dataclass
class TurnContext:
    turn_index: int
    turn_id: str
    turn_dir: Path
    audio_in_dir: Path
    audio_out_dir: Path
    transcripts_dir: Path
    motions_dir: Path
    logs_dir: Path
    wav_in_path: Path
    user_transcript_path: Path
    assistant_response_path: Path
    memory_before_path: Path
    memory_after_path: Path
    turn_meta_path: Path
    wav_prefix: str
    started_ts: str


@dataclass
class SessionContext:
    session_id: str
    session_dir: Path
    memory_dir: Path
    turns_dir: Path
    logs_dir: Path
    meta_path: Path
    memory: Any
    started_ts: str
    started_monotonic: float
    turn_counter: int = 0
    ended_ts: Optional[str] = None
    end_reason: str = ""
    greeting_played: bool = False


# ============================================================
# AUDIO FUNCTIONS
# ============================================================
def record_wav(path: Path, seconds: float, sr: int = RECORD_SR) -> None:
    frames = int(seconds * sr)
    print(f"🎙️ Recording {seconds:.2f}s ...")

    path.parent.mkdir(parents=True, exist_ok=True)

    audio = sd.rec(
        frames,
        samplerate=sr,
        channels=RECORD_CHANNELS,
        dtype=RECORD_DTYPE,
        blocking=True,
    )

    audio_int16 = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio_int16 * 32767).astype(np.int16)

    sf.write(str(path), audio_int16, sr, subtype="PCM_16")
    print(f"✅ Saved input: {path}")


def wait_file_stable(
    path: Path,
    stable_ms: int = FILE_STABLE_MS,
    check_interval_ms: int = FILE_CHECK_MS,
    timeout_ms: int = FILE_TIMEOUT_MS,
) -> None:
    """
    Wait until file size remains unchanged for `stable_ms`.
    """
    last_size = -1
    stable_for = 0
    t0 = time.time()

    while (time.time() - t0) * 1000.0 < timeout_ms:
        try:
            size = os.path.getsize(path)
        except OSError:
            size = -1

        if size > 0 and size == last_size:
            stable_for += check_interval_ms
            if stable_for >= stable_ms:
                return
        else:
            stable_for = 0
            last_size = size

        time.sleep(check_interval_ms / 1000.0)
    # timeout -> proceed


def play_wav_only(path: Path, tail_pad_ms: int = TAIL_PAD_MS,
                  on_audio_started: Optional[Callable[[], None]] = None) -> None:
    """
    Fallback audio-only playback if motion generation fails.
    """
    data, sr = load_wav_for_playback(path, tail_pad_ms=tail_pad_ms)
    sd.play(data, sr)
    try:
        if on_audio_started:
            on_audio_started()
    finally:
        sd.wait()


def _write_pcm16_to_wav(pcm_bytes: bytes, out_path: Path, sample_rate: int = TTS_WAV_SR) -> None:
    """
    Wrap raw PCM 16-bit mono bytes into a standard WAV file.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _collect_audio_bytes(audio_iterable_or_bytes: Any) -> bytes:
    """
    Accept either:
    - bytes
    - bytearray
    - iterable/generator of bytes
    Return a single bytes object.
    """
    if isinstance(audio_iterable_or_bytes, (bytes, bytearray)):
        return bytes(audio_iterable_or_bytes)

    chunks: List[bytes] = []
    for chunk in audio_iterable_or_bytes:
        if isinstance(chunk, (bytes, bytearray)):
            chunks.append(bytes(chunk))
    return b"".join(chunks)


# ============================================================
# OPENAI FUNCTIONS
# ============================================================
def speech_to_text(wav_path: Path) -> str:
    def request(provider_client: Any) -> Any:
        # Reopen the WAV for every key attempt so each request starts at byte 0.
        with wav_path.open("rb") as f:
            return provider_client.audio.transcriptions.create(
                model=STT_MODEL,
                file=f,
            )

    tr = _call_with_credit_failover(
        pool=openai_client_pool,
        is_credit_error=_is_openai_credit_error,
        operation_name="speech_to_text",
        operation=request,
    )
    return (tr.text or "").strip()


def has_real_transcript_text(text: str) -> bool:
    """
    Return True only when STT output contains actual readable text.

    This prevents noise-only recordings, empty strings, or punctuation-only
    transcripts from triggering waiting preset audio.
    """
    text = (text or "").strip()
    if not text:
        return False
    return re.search(r"[0-9A-Za-zÀ-ỹ]", text) is not None


def text_to_speech(text: str, out_path: Path) -> None:
    """
    ElevenLabs TTS:
    - Request PCM 16kHz raw audio
    - Wrap into WAV so downstream code remains unchanged
    """
    def request(provider_client: Any) -> bytes:
        audio_result = provider_client.text_to_speech.convert(
            voice_id=TTS_VOICE_ID,
            text=text,
            model_id=TTS_MODEL,
            language_code=TTS_LANGUAGE_CODE,
            output_format=TTS_OUTPUT_FORMAT,
            voice_settings=VoiceSettings(
                stability=TTS_STABILITY,
                similarity_boost=TTS_SIMILARITY_BOOST,
                style=TTS_STYLE,
                use_speaker_boost=TTS_USE_SPEAKER_BOOST,
                speed=TTS_SPEED,
            ),
        )

        # Consume the generator inside the failover attempt. ElevenLabs may report
        # quota exhaustion during iteration instead of during convert().
        return _collect_audio_bytes(audio_result)

    pcm_bytes = _call_with_credit_failover(
        pool=elevenlabs_client_pool,
        is_credit_error=_is_elevenlabs_credit_error,
        operation_name="text_to_speech",
        operation=request,
    )
    if not pcm_bytes:
        raise RuntimeError("ElevenLabs returned empty audio bytes.")

    _write_pcm16_to_wav(pcm_bytes, out_path, sample_rate=TTS_WAV_SR)


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Returns embeddings as float32 array shape (N, D).
    """
    if not texts:
        return np.zeros((0, 1), dtype=np.float32)

    resp = _call_with_credit_failover(
        pool=openai_client_pool,
        is_credit_error=_is_openai_credit_error,
        operation_name="embed_texts",
        operation=lambda provider_client: provider_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        ),
    )
    vecs = [np.array(item.embedding, dtype=np.float32) for item in resp.data]
    return np.vstack(vecs)


def _iter_openai_response_stream_with_credit_failover(
    model: str,
    input_items: List[Dict[str, str]],
):
    """
    Stream a Responses API request and rotate only on credit/quota exhaustion.

    A failed key is retried with the next key until the first text delta. After a
    text delta has been emitted, replaying the full prompt could duplicate sentences,
    so that rare mid-stream failure stops the current response while the next API
    operation will use the newly selected key.
    """
    last_credit_error: Optional[BaseException] = None

    for index in openai_client_pool.candidate_indices():
        provider_client = openai_client_pool.get_client(index)
        text_started = False

        try:
            with provider_client.responses.stream(model=model, input=input_items) as stream:
                for event in stream:
                    event_type = getattr(event, "type", "")
                    event_error = getattr(event, "error", None)

                    if event_type == "error" and _is_openai_credit_error(event_error):
                        raise _StreamCreditError(event_error)

                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta and not text_started:
                            openai_client_pool.mark_success(index)
                            text_started = True

                    yield event

                stream.close()

            if not text_started:
                openai_client_pool.mark_success(index)
            return

        except Exception as e:
            credit_source = e.provider_error if isinstance(e, _StreamCreditError) else e
            if not _is_openai_credit_error(credit_source):
                raise

            openai_client_pool.mark_credit_exhausted(index)
            last_credit_error = e

            if text_started:
                raise RuntimeError(
                    "OpenAI key ran out of credit after response text streaming had "
                    "started. The key was changed for the next API request; the current "
                    "response was stopped to avoid duplicate sentences."
                ) from e

            continue

    error = openai_client_pool.all_out_of_credit_error("llm_stream")
    if last_credit_error is not None:
        raise error from last_credit_error
    raise error


# ============================================================
# METADATA-AWARE HYBRID RAG - V12.2
# ============================================================

RAG_FIELD_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "Đất đai": (
        "đất đai", "sổ đỏ", "sổ hồng", "quyền sử dụng đất", "tách thửa",
        "hợp thửa", "chuyển mục đích sử dụng đất", "tranh chấp đất",
        "giấy chứng nhận quyền sử dụng đất",
    ),
    "Hộ tịch": (
        "hộ tịch", "khai sinh", "khai tử", "kết hôn", "đăng ký kết hôn",
        "xác nhận tình trạng hôn nhân", "nhận cha mẹ con", "cải chính hộ tịch",
        "thay đổi hộ tịch", "đăng ký lại khai sinh",
    ),
    "Chứng thực": (
        "chứng thực", "sao y", "bản sao", "chứng thực chữ ký", "chứng thực hợp đồng",
    ),
    "Hộ kinh doanh": (
        "hộ kinh doanh", "kinh doanh cá thể", "đăng ký hộ kinh doanh",
        "mở quán", "mở cửa hàng", "mở tiệm",
    ),
    "Hợp tác xã": (
        "hợp tác xã", "liên hiệp hợp tác xã", "htx",
    ),
    "Giáo dục và đào tạo": (
        "giáo dục", "trường học", "mầm non", "mẫu giáo", "nhà trẻ",
        "tiểu học", "trung học", "cơ sở giáo dục",
    ),
    "Người có công": (
        "người có công", "thương binh", "liệt sĩ", "bà mẹ việt nam anh hùng",
        "gia đình liệt sĩ", "ưu đãi người có công",
    ),
    "Bảo trợ xã hội": (
        "bảo trợ xã hội", "trợ cấp xã hội", "đối tượng bảo trợ",
        "người cao tuổi", "người khuyết tật",
    ),
    "Giảm nghèo": (
        "giảm nghèo", "hộ nghèo", "hộ cận nghèo",
    ),
    "Tôn giáo": (
        "tôn giáo", "tín ngưỡng", "cơ sở tôn giáo",
    ),
    "Hội - Quỹ": (
        "hội", "quỹ xã hội", "quỹ từ thiện", "thành lập hội",
    ),
    "Thi đua - Khen thưởng": (
        "thi đua", "khen thưởng", "bằng khen", "giấy khen",
    ),
    "Phòng, chống tệ nạn xã hội": (
        "tệ nạn xã hội", "cai nghiện", "ma túy", "phòng chống tệ nạn",
    ),
    "Văn hóa - Thể thao - Trẻ em": (
        "văn hóa", "thể thao", "trẻ em", "gia đình", "hoạt động văn hóa",
    ),
    "Di sản văn hóa": (
        "di sản", "di tích", "di sản văn hóa",
    ),
    "Hòa giải ở cơ sở": (
        "hòa giải ở cơ sở", "hòa giải viên", "tổ hòa giải",
    ),
    "Bồi thường nhà nước": (
        "bồi thường nhà nước", "yêu cầu bồi thường",
    ),
    "Xây dựng": (
        "xây dựng", "giấy phép xây dựng", "công trình xây dựng",
    ),
    "Quy hoạch đô thị": (
        "quy hoạch đô thị", "quy hoạch", "quy hoạch xây dựng",
    ),
    "Nhà ở": (
        "nhà ở", "nhà chung cư", "chung cư",
    ),
    "Đường bộ": (
        "đường bộ", "giao thông đường bộ", "đường giao thông",
    ),
    "Đường thủy nội địa": (
        "đường thủy", "đường thủy nội địa", "bến thủy", "phương tiện thủy",
    ),
    "Thủy lợi": (
        "thủy lợi", "công trình thủy lợi",
    ),
    "Thủy sản": (
        "thủy sản", "nuôi trồng thủy sản", "khai thác thủy sản",
    ),
    "Chăn nuôi - Thú y": (
        "chăn nuôi", "thú y", "vật nuôi", "dịch bệnh động vật",
    ),
    "Phát triển nông thôn": (
        "phát triển nông thôn", "nông thôn",
    ),
    "Biển đảo - An toàn hồ chứa": (
        "biển đảo", "an toàn hồ chứa", "hồ chứa",
    ),
    "Ứng phó sự cố tràn dầu": (
        "tràn dầu", "sự cố tràn dầu",
    ),
    "Môi trường": (
        "môi trường", "ô nhiễm", "bảo vệ môi trường",
    ),
    "Tài nguyên nước": (
        "tài nguyên nước", "nguồn nước", "khai thác nước",
    ),
    "Khoáng sản": (
        "khoáng sản", "khai thác khoáng sản",
    ),
    "Quản lý công sản": (
        "công sản", "tài sản công", "quản lý tài sản công",
    ),
    "Phí - Lệ phí": (
        "phí lệ phí", "lệ phí", "thu phí",
    ),
    "Tiêu dùng": (
        "tiêu dùng", "quyền lợi người tiêu dùng", "bảo vệ người tiêu dùng",
    ),
    "Quy định chung về thủ tục hành chính / một cửa": (
        "một cửa", "bộ phận một cửa", "trung tâm phục vụ hành chính công",
        "dịch vụ công", "thủ tục hành chính",
    ),
}

# Ambiguous/generic aliases are intentionally excluded from field boosts.
# In V12.1, accent stripping made "hội" and "hỏi" identical ("hoi"), which
# could incorrectly route a normal phrase such as "Cho tôi hỏi..." to Hội - Quỹ.
# These concepts are still handled by semantic procedure routing.
RAG_RISKY_FIELD_ALIASES = {
    "hoi", "gia dinh", "le phi", "phi", "moi truong", "nha o",
    "quy hoach", "giao duc", "van hoa", "the thao", "tre em",
    "nong thon", "nguon nuoc", "thu tuc hanh chinh", "dich vu cong",
}

# Query phrases for MULTI-intent detection. These are deliberately more
# specific than V12.1 so "Nộp hồ sơ ở đâu?" is WHERE, not DOCUMENTS merely
# because it contains the word "hồ sơ".
RAG_INTENT_QUERY_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "documents": (
        "hồ sơ gồm", "thành phần hồ sơ", "hồ sơ cần", "chuẩn bị hồ sơ",
        "giấy tờ", "mang theo", "nộp kèm", "bộ hồ sơ",
    ),
    "time": (
        "bao lâu", "bao nhiêu ngày", "mấy ngày", "mấy hôm", "thời gian",
        "thời hạn", "khi nào", "chờ khoảng",
    ),
    "fee": (
        "phí", "lệ phí", "tiền", "chi phí", "tốn", "khoản phải nộp",
        "khoản tiền", "có thu",
    ),
    "where": (
        "ở đâu", "đến đâu", "chỗ nào", "nơi nào", "tiếp nhận", "online",
        "trực tuyến", "bưu điện", "nộp qua",
    ),
    "steps": (
        "các bước", "trước sau", "làm gì trước", "làm gì sau", "cách làm",
        "quy trình", "trình tự", "hướng dẫn", "từ đầu",
    ),
    "form": (
        "mẫu đơn", "mẫu giấy", "biểu mẫu", "tờ khai", "tờ nào", "đơn nào", "phải điền",
    ),
    "condition": (
        "điều kiện", "đáp ứng", "ai được", "yêu cầu bắt buộc", "đối tượng thực hiện",
        "trường hợp nào",
    ),
    "result": (
        "nhận được", "được nhận", "được cấp", "cấp hoặc trả", "trả cho tôi",
        "kết quả cuối", "hoàn tất", "xử lý xong",
    ),
    "legal": (
        "văn bản", "luật nào", "theo luật", "quy định pháp luật", "căn cứ",
        "cơ sở pháp lý", "quy định nào",
    ),
}

# Metadata section labels -> answer intent. One section may satisfy several
# intents, e.g. "Nơi tiếp nhận, trả kết quả, thời gian và lệ phí".
RAG_INTENT_SECTION_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "documents": (
        "thành phần hồ sơ", "thành phần, số lượng hồ sơ", "hồ sơ cần lưu", "hồ sơ lưu",
    ),
    "time": (
        "thời hạn", "thời gian thực hiện", "thời hạn/thời gian giải quyết",
        "nơi tiếp nhận, trả kết quả, thời gian và lệ phí",
    ),
    "fee": (
        "lệ phí", "phí, lệ phí", "nơi tiếp nhận, trả kết quả, thời gian và lệ phí",
    ),
    "where": (
        "cách thức thực hiện", "hình thức thực hiện", "cơ quan thực hiện",
        "nơi tiếp nhận, trả kết quả", "nơi tiếp nhận, trả kết quả, thời gian và lệ phí",
    ),
    "steps": (
        "trình tự thực hiện", "trình tự xử lý công việc", "quy trình nội bộ", "quy trình điện tử",
    ),
    "form": (
        "tên mẫu đơn, mẫu tờ khai", "biểu mẫu", "biểu mẫu và hồ sơ lưu",
    ),
    "condition": (
        "yêu cầu, điều kiện", "đối tượng thực hiện",
    ),
    "result": (
        "kết quả thực hiện", "kết quả giải quyết", "kết quả",
    ),
    "legal": (
        "căn cứ pháp lý", "cơ sở pháp lý",
    ),
}

# For the legacy 2304.pdf rows only, use body-content checks before trusting a
# section label. New source_path rows are already structured by the new parser.
RAG_LEGACY_SECTION_BODY_MARKERS: Dict[str, Tuple[str, ...]] = {
    "documents": ("hồ sơ", "thành phần", "giấy tờ"),
    "time": ("thời hạn", "thời gian", "ngày", "giờ"),
    "fee": ("phí", "lệ phí", "không quy định"),
    "where": ("nộp", "trực tiếp", "trực tuyến", "cơ quan", "tiếp nhận", "bưu chính"),
    "steps": ("bước", "trình tự", "thực hiện", "quy trình"),
    "form": ("mẫu", "tờ khai", "biểu mẫu"),
    "condition": ("điều kiện", "yêu cầu", "đối tượng"),
    "result": ("kết quả", "quyết định", "giấy", "chứng nhận"),
    "legal": ("luật", "nghị định", "thông tư", "quyết định", "căn cứ"),
}

RAG_QUERY_STOPWORDS = {
    "toi", "quy", "khach", "muon", "can", "hoi", "cho", "biet", "ve", "la",
    "thi", "va", "hoac", "cua", "co", "khong", "duoc", "lam", "the", "nao",
    "nhu", "gi", "mot", "cac", "nhung", "nay", "do", "o", "tai", "xin",
    "giup", "minh", "phai",
}

RAG_PROCEDURE_ACTION_PREFIXES: Tuple[str, ...] = (
    "Giải quyết", "Đăng ký", "Cấp", "Tách", "Đính chính", "Thu hồi", "Cung cấp",
    "Thẩm định", "Giao", "Chuyển", "Điều chỉnh", "Tổ chức", "Sử dụng", "Xác nhận", "Xác định",
    "Tặng cho", "Hòa giải", "Công nhận", "Cho phép", "Chấp thuận", "Xóa", "Thông báo",
    "Thành lập", "Đề nghị", "Phê duyệt", "Gia hạn", "Đổi", "Cấp lại", "Cấp đổi",
    "Đăng ký lại", "Công bố", "Tiếp nhận", "Cấp mới", "Chấm dứt", "Khôi phục",
    "Thay đổi", "Sáp nhập", "Hợp nhất", "Giải thể",
)


@dataclass
class RAGRoute:
    # List fields must be declared before the attribute named `field`, otherwise
    # the class attribute would shadow dataclasses.field() during class creation.
    intents: List[str] = field(default_factory=list)
    missing_intents: List[str] = field(default_factory=list)
    candidate_procedures: List[str] = field(default_factory=list)
    field: str = ""
    procedure_name: str = ""
    procedure_key: str = ""
    administrative_level: str = ""
    intent: str = ""                 # first intent, backward-compatible
    route_method: str = ""
    field_score: float = 0.0
    procedure_score: float = 0.0
    procedure_margin: float = 0.0
    needs_clarification: bool = False
    clarification_reason: str = ""


@dataclass
class RAGRetrievalResult:
    hits: List[Dict[str, Any]]
    route: RAGRoute
    kb_relevant: bool
    confidence: float
    low_confidence: bool
    debug: Dict[str, Any] = field(default_factory=dict)


def _rag_normalize_text(text: str) -> str:
    text = (text or "").strip().lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _rag_tokens(text: str) -> List[str]:
    return [
        token for token in _rag_normalize_text(text).split()
        if len(token) >= 2 and token not in RAG_QUERY_STOPWORDS
    ]


def _rag_phrase_present(normalized_query: str, phrase: str) -> bool:
    p = _rag_normalize_text(phrase)
    return bool(p) and f" {p} " in f" {normalized_query} "


def _rag_lexical_similarity(query_text: str, candidate_text: str) -> float:
    qn = _rag_normalize_text(query_text)
    cn = _rag_normalize_text(candidate_text)
    if not qn or not cn:
        return 0.0
    if cn in qn:
        return 1.0
    q_tokens = set(_rag_tokens(qn))
    c_tokens = set(_rag_tokens(cn))
    if not q_tokens or not c_tokens:
        return 0.0
    common = len(q_tokens & c_tokens)
    if common == 0:
        return 0.0
    coverage_candidate = common / max(1, len(c_tokens))
    coverage_query = common / max(1, len(q_tokens))
    jaccard = common / max(1, len(q_tokens | c_tokens))
    return float(min(1.0, 0.50 * coverage_candidate + 0.30 * coverage_query + 0.20 * jaccard))


def _rag_intent_focus_text(query_text: str, procedure_name: str = "") -> str:
    """
    Focus intent detection on the citizen's actual question, not on words inside
    a long administrative procedure title.

    V12.2:
    - Strong separators such as an em dash or a topic colon are respected.
    - If the chosen procedure name occurs in the query, remove it before
      classifying the requested information.
    - With normal STT sentence punctuation, use the final question sentence.
    - For one-sentence topic framing, find the first comma that starts an actual
      citizen question and keep everything after it (including multi-intent clauses).
    """
    raw = (query_text or "").strip()
    if not raw:
        return ""

    if "—" in raw:
        tail = raw.rsplit("—", 1)[-1].strip()
        if tail:
            return tail

    if ":" in raw and re.match(
        r"^\s*(liên quan|về|đối với|với thủ tục)\b",
        raw,
        flags=re.IGNORECASE,
    ):
        tail = raw.rsplit(":", 1)[-1].strip()
        if tail:
            return tail

    qn_full = _rag_normalize_text(raw)
    pn = _rag_normalize_text(procedure_name)

    if pn and pn in qn_full:
        cleaned = re.sub(r"\s+", " ", qn_full.replace(pn, " ")).strip()
        cleaned = re.sub(
            r"^(toi can hoi chuyen|toi muon lam thu tuc|cho toi hoi ve thu tuc|"
            r"truong hop cua toi la|xin tu van giup toi ve viec|lien quan den|"
            r"lien quan toi|lien quan thu tuc|ve viec|doi voi|voi viec|"
            r"voi thu tuc|toi dang tim hieu ve|toi dang can|toi hoi ve|"
            r"toi can tu van ve)\s+",
            "",
            cleaned,
        ).strip()
        if len(cleaned.split()) <= 65:
            return cleaned

    parts = [
        p.strip()
        for p in re.split(r"(?<=[.!?])\s+", raw)
        if p.strip()
    ]
    if len(parts) >= 2:
        return parts[-1]

    # Prefix-based single-sentence framing. We do not simply use the last comma,
    # because official procedure names themselves often contain commas.
    if re.match(
        r"^\s*(về việc|liên quan đến|liên quan tới|đối với|với việc|với thủ tục)\b",
        raw,
        flags=re.IGNORECASE,
    ):
        question_start_pattern = (
            r"(?:toi|can|co|bo|muc|thuong|tu|bao|xin|thu tuc|nhung|sau|"
            r"ket qua|co so|quy dinh|toi phai|phai|noi|cho|khoan|thoi|ai|"
            r"doi tuong|qua trinh|van ban|lam|viec|cuoi)"
        )
        for match in re.finditer(",", raw):
            tail = raw[match.end():].strip()
            if re.match(
                rf"^{question_start_pattern}\b",
                _rag_normalize_text(tail),
            ):
                return tail

    qn = qn_full
    if pn and pn in qn:
        qn = re.sub(r"\s+", " ", qn.replace(pn, " ")).strip()

    # Last-resort bounded tail for STT text without useful punctuation.
    return " ".join(qn.split()[-55:])


def _rag_detect_section_intents(
    query_text: str,
    procedure_name: str = "",
) -> List[str]:
    """
    Detect one or more requested information types.

    The classifier is contextual rather than simple keyword matching:
    - "nộp hồ sơ ở đâu" -> WHERE, not DOCUMENTS.
    - "nhận kết quả ở đâu" -> WHERE, not RESULT.
    - "cơ quan trả cho tôi giấy gì" -> RESULT.
    - Multi-intent questions return multiple intent labels.
    """
    qn = _rag_normalize_text(
        _rag_intent_focus_text(
            query_text,
            procedure_name=procedure_name,
        )
    )
    if not qn:
        return []

    def has(pattern: str) -> bool:
        return re.search(pattern, qn) is not None

    found: List[str] = []

    # --------------------------------------------------------
    # 1) Documents / dossier composition
    # --------------------------------------------------------
    strong_documents = (
        has(r"\b(thanh phan ho so|bo ho so)\b")
        or has(
            r"\bho so\b.{0,35}\b("
            r"gom|can nhung|co nhung|nhung gi|gi gom|can co|ra sao|the nao"
            r")\b"
        )
        or has(
            r"\b(chuan bi|can)\b.{0,30}\b(ho so|giay to|tai lieu)\b"
        )
        or has(
            r"\b(mang theo nhung gi|dem theo|nop kem|can nop gi|"
            r"phai nop gi|nhung gi can nop)\b"
        )
        or has(
            r"\b(tai lieu|giay to)\b.{0,30}\b("
            r"nao|gi|phai kem|kem trong|can co|can nop"
            r")\b"
        )
        or has(
            r"\b(phai kem|kem theo)\b.{0,25}\b(ho so|tai lieu|giay to)\b"
        )
    )
    generic_documents = has(
        r"\bgiay to\b.{0,25}\b(can|nao|gi|chuan bi|gom)\b"
    )
    returned_document = has(
        r"\b(co quan )?(tra|cap|nhan)\b.{0,30}\b(cho toi )?giay to\b"
    )

    if strong_documents or (generic_documents and not returned_document):
        found.append("documents")

    # --------------------------------------------------------
    # 2) Time
    # --------------------------------------------------------
    if has(
        r"\b(bao lau|bao nhieu lau|doi bao nhieu lau|bao nhieu ngay|"
        r"may ngay|may hom|thoi gian|thoi han|khi nao|bao gio|"
        r"cho khoang|mat lau|moi xong|thi xong)\b"
    ):
        found.append("time")

    # --------------------------------------------------------
    # 3) Fee
    # --------------------------------------------------------
    if (
        has(
            r"\b(le phi|chi phi|ton tien|mat tien|khoan tien|"
            r"khoan phai nop|phi|dong bao nhieu|phai dong|nop bao nhieu|"
            r"thu tien|co thu|tong tien|tien phai nop|so tien)\b"
        )
        or has(
            r"\bthanh toan\b.{0,25}\b(bao nhieu|phi|le phi|tien)\b"
        )
    ):
        found.append("fee")

    # --------------------------------------------------------
    # 4) Submission / receiving place or channel
    # --------------------------------------------------------
    if (
        has(
            r"\b(o dau|den dau|cho nao|noi nao|co quan nao|bo phan nao|"
            r"noi nop|cho nop|dia chi|dia diem nao)\b"
        )
        or has(r"\b(nop|gui)\b.{0,14}\b(tai|qua)\b")
        or has(
            r"\b(online|truc tuyen|qua mang|tren mang|nop dien tu|"
            r"dien tu|buu dien|buu chinh|dich vu cong|tiep nhan|"
            r"nhan ho so)\b"
        )
    ):
        found.append("where")

    # --------------------------------------------------------
    # 5) Steps / sequence
    # --------------------------------------------------------
    if (
        has(
            r"\b(cac buoc|tung buoc|thu tu cac buoc|thu tu nao|"
            r"tu buoc nao|buoc nao|quy trinh|trinh tu|huong dan|"
            r"cach lam|cach thuc hien|lam the nao|lam nhu the nao|"
            r"lam sao|thuc hien the nao|thuc hien nhu the nao|"
            r"thuc hien ra sao|lam gi truoc|lam gi sau|truoc sau|"
            r"tu dau|bat dau tu dau)\b"
        )
        or has(
            r"\b(bat dau|thuc hien|qua trinh)\b.{0,45}\b("
            r"the nao|nhu the nao|ra sao|thu tu nao|buoc nao"
            r")\b"
        )
    ):
        found.append("steps")

    # --------------------------------------------------------
    # 6) Form / declaration
    # --------------------------------------------------------
    if (
        has(
            r"\b(mau don|mau giay|bieu mau|to khai|mau nao|dung mau|"
            r"dien mau|phai dien|to khai nao|don nao|khai to nao)\b"
        )
        or has(r"\bmau giay\b.{0,30}\b(dien|khai)\b")
    ):
        found.append("form")

    # --------------------------------------------------------
    # 7) Eligibility / condition
    # --------------------------------------------------------
    if (
        has(
            r"\b(dieu kien|dap ung|yeu cau|doi tuong|truong hop nao|"
            r"ap dung cho ai|du dieu kien|thoa man)\b"
        )
        or has(
            r"\bai\b.{0,30}\b("
            r"duoc|co the|thuoc|phep|lam thu tuc|thuc hien|du dieu kien"
            r")\b"
        )
    ):
        found.append("condition")

    # --------------------------------------------------------
    # 8) Result type
    # --------------------------------------------------------
    if (
        has(
            r"\bket qua( giai quyet| cuoi| cuoi cung)?\b.{0,35}\b("
            r"la gi|duoc gi|gom gi|ra sao|the nao|"
            r"la (loai )?(van ban|giay|quyet dinh|chung nhan) gi"
            r")\b"
        )
        or has(
            r"\bnhan ket qua\b.{0,18}\b(nhu the nao|the nao|ra sao)\b"
        )
        or has(
            r"\b(co quan )?(cap|tra)\b.{0,35}\b(cho toi )?("
            r"gi|giay|quyet dinh|chung nhan|van ban"
            r")\b"
        )
        or has(
            r"\b(xu ly xong|giai quyet xong|hoan tat|cuoi cung|"
            r"cuoi thu tuc|ket thuc)\b.{0,45}\b(nhan|cap|tra|duoc cap)\b"
        )
        or has(
            r"\b(nhan duoc|duoc nhan|se nhan|duoc tra|duoc cap)\b"
            r".{0,30}\b(cai gi|gi|giay|quyet dinh|chung nhan|van ban)\b"
        )
        or has(
            r"\bnhan\b.{0,30}\b(giay to|quyet dinh|van ban|chung nhan)\b"
            r".{0,20}\b(gi|nao)\b"
        )
    ):
        found.append("result")

    # --------------------------------------------------------
    # 9) Legal basis
    # --------------------------------------------------------
    if (
        has(
            r"\b(luat nao|theo luat|quy dinh phap luat|can cu|"
            r"co so phap ly|quy dinh nao|nghi dinh nao|thong tu nao|"
            r"luat hay nghi dinh|nghi dinh hoac thong tu|"
            r"theo quy dinh nao|dua tren)\b"
        )
        or has(
            r"\b(van ban|luat|nghi dinh|thong tu)\b.{0,35}\b("
            r"phap luat|quy dinh|lam can cu|can cu|dieu chinh|huong dan"
            r")\b"
        )
        or has(r"\bquy dinh\b.{0,30}\b(van ban nao|viec nay)\b")
    ):
        found.append("legal")

    return found


def _rag_detect_admin_level(query_text: str) -> str:
    qn = _rag_normalize_text(query_text)
    if any(_rag_phrase_present(qn, p) for p in (
        "cấp xã", "ủy ban nhân dân xã", "ủy ban nhân dân phường", "ubnd xã", "ubnd phường", "tại xã", "tại phường",
    )):
        return "Cấp xã"
    if any(_rag_phrase_present(qn, p) for p in (
        "cấp tỉnh", "ủy ban nhân dân tỉnh", "ubnd tỉnh", "tại tỉnh",
    )):
        return "Cấp tỉnh"
    if any(_rag_phrase_present(qn, p) for p in (
        "cấp trung ương", "bộ nông nghiệp", "bộ trưởng", "trung ương",
    )):
        return "Cấp trung ương"
    return ""


def _rag_is_list_query(query_text: str) -> bool:
    qn = _rag_normalize_text(query_text)
    return any(_rag_phrase_present(qn, p) for p in (
        "có những thủ tục nào", "có các thủ tục nào", "danh sách thủ tục",
        "những thủ tục gì", "các thủ tục gì", "tất cả thủ tục",
    ))


def _rag_parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _rag_canonicalize_procedure_name(name: str) -> str:
    """Repair known legacy parser contamination in RAM; never edits kb_meta.json."""
    text = " ".join((name or "").split()).strip()
    if not text:
        return ""
    action_alt = "|".join(
        re.escape(x) for x in sorted(RAG_PROCEDURE_ACTION_PREFIXES, key=len, reverse=True)
    )
    pattern = re.compile(
        rf"(?:^|\s)\d{{1,3}}\.\s+((?:{action_alt})\b.*)$",
        flags=re.IGNORECASE | re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if matches:
        tail = matches[-1].group(1).strip()
        if len(tail) >= 12:
            return tail
    return re.sub(r"^\d{1,3}\.\s*", "", text).strip()


def _rag_extract_source_body(meta_row: Dict[str, Any]) -> str:
    text = str(meta_row.get("text", "") or "")
    pos = text.rfind("Mục thông tin:")
    if pos >= 0:
        sub = text[pos:]
        blank = sub.find("\n\n")
        if blank >= 0:
            return sub[blank + 2:]
    parts = text.split("\n\n")
    return parts[-1] if parts else text


def _rag_section_intents_from_name(section_name: str) -> List[str]:
    sn = _rag_normalize_text(section_name)
    result: List[str] = []
    for intent, patterns in RAG_INTENT_SECTION_PATTERNS.items():
        for pattern in patterns:
            pn = _rag_normalize_text(pattern)
            if pn and (pn in sn or sn in pn):
                result.append(intent)
                break
    return result


def _rag_row_reliable_for_intent(meta_row: Dict[str, Any], intent: str) -> bool:
    if intent not in _rag_section_intents_from_name(str(meta_row.get("section_name", "") or "")):
        return False
    # New parser rows have source_path and structured section labels.
    if str(meta_row.get("source_path", "") or "").strip():
        return True
    # Legacy 2304.pdf rows may have section numbers from form instructions.
    body_norm = _rag_normalize_text(_rag_extract_source_body(meta_row))
    return any(
        _rag_normalize_text(marker) in body_norm
        for marker in RAG_LEGACY_SECTION_BODY_MARKERS.get(intent, ())
    )


def _rag_field_soft_keyword_scores(query_text: str, available_fields: set[str]) -> Dict[str, float]:
    qn = _rag_normalize_text(query_text)
    scores: Dict[str, float] = {}
    for field_name in available_fields:
        phrases = [field_name]
        phrases.extend(RAG_FIELD_KEYWORDS.get(field_name, ()))
        best = 0.0
        for phrase in phrases:
            pn = _rag_normalize_text(phrase)
            if not pn or pn in RAG_RISKY_FIELD_ALIASES:
                continue
            if not _rag_phrase_present(qn, pn):
                continue
            token_count = len(pn.split())
            score = (0.07 if token_count >= 2 else 0.02) + 0.008 * min(4, token_count)
            best = max(best, score)
        if best > 0.0:
            scores[field_name] = best
    return scores


class LocalKBStore:
    """V12.2 metadata-aware RAG. KB files remain kb_meta.json + kb_vectors.npy."""

    def __init__(self, kb_dir: Path):
        self.kb_dir = kb_dir
        self.meta_path = kb_dir / "kb_meta.json"
        self.vec_path = kb_dir / "kb_vectors.npy"
        self._meta: List[Dict[str, Any]] = []
        self._vecs: Optional[np.ndarray] = None
        self._vecs_norm: Optional[np.ndarray] = None
        self._field_indices: Dict[str, np.ndarray] = {}
        self._field_centroid_names: List[str] = []
        self._field_centroids: Optional[np.ndarray] = None
        self._proc_keys: List[Tuple[str, str]] = []
        self._proc_indices: Dict[Tuple[str, str], np.ndarray] = {}
        self._proc_anchor_indices: Dict[Tuple[str, str], np.ndarray] = {}
        self._proc_display: Dict[Tuple[str, str], str] = {}
        self._proc_centroids: Optional[np.ndarray] = None
        self._reliable_section_indices: Dict[Tuple[Tuple[str, str], str], np.ndarray] = {}
        self._row_proc_key: List[Optional[Tuple[str, str]]] = []
        self._available_fields: set[str] = set()
        self._load()

    @staticmethod
    def _normalize_rows(mat: np.ndarray) -> np.ndarray:
        if mat.size == 0:
            return mat
        return mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)

    @staticmethod
    def _normalize_vector(vec: np.ndarray) -> np.ndarray:
        return vec / (float(np.linalg.norm(vec)) + 1e-12)

    def _load(self) -> None:
        try:
            loaded = json.loads(self.meta_path.read_text(encoding="utf-8-sig")) if self.meta_path.exists() else []
            self._meta = loaded if isinstance(loaded, list) else []
        except Exception:
            self._meta = []
        try:
            self._vecs = np.load(self.vec_path, allow_pickle=False) if self.vec_path.exists() else None
            if self._vecs is not None and self._vecs.dtype != np.float32:
                self._vecs = self._vecs.astype(np.float32)
        except Exception:
            self._vecs = None
        if self._vecs is not None and (self._vecs.ndim != 2 or len(self._meta) != self._vecs.shape[0]):
            print("[RAG] KB metadata/vector mismatch. Disable KB for safety.")
            self._meta = []
            self._vecs = None
        self._build_metadata_indices()

    def _save(self) -> None:
        self.meta_path.write_text(json.dumps(self._meta, ensure_ascii=False, indent=2), encoding="utf-8")
        if self._vecs is None:
            if self.vec_path.exists():
                try:
                    self.vec_path.unlink()
                except Exception:
                    pass
        else:
            np.save(self.vec_path, self._vecs)
        self._build_metadata_indices()

    def add_documents(self, texts: List[str], source: str = "manual") -> None:
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            return
        vecs_new = embed_texts(texts)
        meta_new = [{"id": f"{int(time.time() * 1000)}_{i}", "source": source, "text": t, "ts": time.strftime("%Y-%m-%d %H:%M:%S")} for i, t in enumerate(texts)]
        if self._vecs is None:
            self._vecs = vecs_new
            self._meta = meta_new
        else:
            self._vecs = np.vstack([self._vecs, vecs_new])
            self._meta.extend(meta_new)
        self._save()

    def _build_metadata_indices(self) -> None:
        self._field_indices = {}
        self._field_centroid_names = []
        self._field_centroids = None
        self._proc_keys = []
        self._proc_indices = {}
        self._proc_anchor_indices = {}
        self._proc_display = {}
        self._proc_centroids = None
        self._reliable_section_indices = {}
        self._row_proc_key = [None] * len(self._meta)
        self._available_fields = set()
        self._vecs_norm = None
        if self._vecs is None or not self._meta:
            print("[RAG] KB is empty or unavailable.")
            return
        self._vecs_norm = self._normalize_rows(self._vecs)
        field_groups: Dict[str, List[int]] = {}
        proc_groups: Dict[Tuple[str, str], List[int]] = {}
        display_candidates: Dict[Tuple[str, str], List[Tuple[bool, str]]] = {}
        for i, m in enumerate(self._meta):
            field_name = str(m.get("field", "") or "").strip()
            raw_proc = str(m.get("procedure_name", "") or "").strip()
            canonical_proc = _rag_canonicalize_procedure_name(raw_proc)
            if field_name:
                field_groups.setdefault(field_name, []).append(i)
                self._available_fields.add(field_name)
            if canonical_proc:
                key = (field_name, _rag_normalize_text(canonical_proc))
                proc_groups.setdefault(key, []).append(i)
                display_candidates.setdefault(key, []).append((bool(str(m.get("source_path", "") or "").strip()), canonical_proc))
                self._row_proc_key[i] = key

        self._field_indices = {k: np.asarray(v, dtype=np.int64) for k, v in field_groups.items()}
        self._proc_indices = {k: np.asarray(v, dtype=np.int64) for k, v in proc_groups.items()}

        # Representative procedure name: prefer the new parser name; otherwise the
        # most frequent cleaned legacy name. This does not alter the JSON file.
        for key, values in display_candidates.items():
            preferred = [name for is_new, name in values if is_new] or [name for _, name in values]
            counts: Dict[str, int] = {}
            for name in preferred:
                counts[name] = counts.get(name, 0) + 1
            self._proc_display[key] = sorted(counts, key=lambda x: (-counts[x], len(x), x))[0]

        proc_centroids: List[np.ndarray] = []
        proc_keys: List[Tuple[str, str]] = []
        for key, indices in self._proc_indices.items():
            anchors: List[int] = []
            for idx in indices:
                m = self._meta[int(idx)]
                section_intents = _rag_section_intents_from_name(str(m.get("section_name", "") or ""))
                content_type = str(m.get("content_type", "") or "").strip()
                is_new = bool(str(m.get("source_path", "") or "").strip())
                if is_new:
                    if section_intents or content_type in ("procedure_section", "document_section"):
                        anchors.append(int(idx))
                else:
                    if any(_rag_row_reliable_for_intent(m, intent) for intent in section_intents):
                        anchors.append(int(idx))
            if not anchors:
                anchors = [int(x) for x in indices]
            anchor_arr = np.asarray(anchors, dtype=np.int64)
            self._proc_anchor_indices[key] = anchor_arr
            centroid = self._normalize_vector(np.mean(self._vecs_norm[anchor_arr], axis=0))
            proc_keys.append(key)
            proc_centroids.append(centroid.astype(np.float32))
            for intent in RAG_INTENT_SECTION_PATTERNS:
                reliable = [int(idx) for idx in indices if _rag_row_reliable_for_intent(self._meta[int(idx)], intent)]
                if reliable:
                    self._reliable_section_indices[(key, intent)] = np.asarray(reliable, dtype=np.int64)

        self._proc_keys = proc_keys
        if proc_centroids:
            self._proc_centroids = np.vstack(proc_centroids).astype(np.float32)

        # Balanced field centroids built from canonical procedure centroids, so a
        # field with many repeated chunks cannot dominate its semantic center.
        if self._proc_centroids is not None:
            by_field: Dict[str, List[int]] = {}
            for j, key in enumerate(self._proc_keys):
                if key[0]:
                    by_field.setdefault(key[0], []).append(j)
            field_names: List[str] = []
            field_centroids: List[np.ndarray] = []
            for field_name, js in by_field.items():
                field_names.append(field_name)
                field_centroids.append(self._normalize_vector(np.mean(self._proc_centroids[js], axis=0)).astype(np.float32))
            if field_centroids:
                self._field_centroid_names = field_names
                self._field_centroids = np.vstack(field_centroids).astype(np.float32)

        print(
            f"[RAG V12.2] Loaded {len(self._meta)} chunks | "
            f"fields={len(self._field_indices)} | canonical_procedures={len(self._proc_indices)}"
        )

    def _procedure_candidates(self, query_text: str, qv_norm: np.ndarray, sims: np.ndarray, limit: int = RAG_ROUTE_CANDIDATE_K) -> List[Dict[str, Any]]:
        if self._proc_centroids is None or not self._proc_keys:
            return []
        centroid_scores = (self._proc_centroids @ qv_norm.reshape(-1, 1)).reshape(-1)
        field_boosts = _rag_field_soft_keyword_scores(query_text, self._available_fields)
        rows: List[Dict[str, Any]] = []
        for j, key in enumerate(self._proc_keys):
            anchor_indices = self._proc_anchor_indices[key]
            anchor_scores = sims[anchor_indices]
            if len(anchor_scores) == 1:
                top1 = top2 = float(anchor_scores[0])
            else:
                pair = np.partition(anchor_scores, -2)[-2:]
                top1 = float(np.max(pair))
                top2 = float(np.min(pair))
            display = self._proc_display[key]
            lexical = _rag_lexical_similarity(query_text, display)
            field_boost = float(field_boosts.get(key[0], 0.0))
            combined = (
                RAG_PROC_CENTROID_WEIGHT * float(centroid_scores[j])
                + RAG_PROC_TOP_CHUNK_WEIGHT * top1
                + RAG_PROC_SECOND_CHUNK_WEIGHT * top2
                + RAG_PROC_LEXICAL_WEIGHT * lexical
                + RAG_FIELD_KEYWORD_SCALE * field_boost
            )
            rows.append({
                "key": key, "field": key[0], "procedure_name": display,
                "score": float(combined), "centroid_score": float(centroid_scores[j]),
                "top_chunk_score": top1, "second_chunk_score": top2,
                "lexical_score": float(lexical), "field_keyword_boost": field_boost,
            })
        rows.sort(key=lambda x: x["score"], reverse=True)
        return rows[:max(1, int(limit))]

    def _field_for_list_query(self, query_text: str, qv_norm: np.ndarray) -> Tuple[str, float]:
        if self._field_centroids is None or not self._field_centroid_names:
            return "", 0.0
        sem = (self._field_centroids @ qv_norm.reshape(-1, 1)).reshape(-1)
        boosts = _rag_field_soft_keyword_scores(query_text, self._available_fields)
        best_name = ""
        best_score = -1.0
        for i, name in enumerate(self._field_centroid_names):
            score = float(sem[i]) + RAG_FIELD_KEYWORD_SCALE * float(boosts.get(name, 0.0))
            if score > best_score:
                best_name, best_score = name, score
        return best_name, best_score

    def _llm_route_fallback(self, query_text: str, procedure_candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not RAG_ENABLE_LLM_FALLBACK or not procedure_candidates:
            return None
        proc_items = [{"field": x["field"], "procedure_name": x["procedure_name"]} for x in procedure_candidates[:RAG_LLM_PROCEDURE_CANDIDATES]]
        field_names: List[str] = []
        for item in proc_items:
            if item["field"] and item["field"] not in field_names:
                field_names.append(item["field"])
            if len(field_names) >= RAG_LLM_FIELD_CANDIDATES:
                break
        prompt = [
            {"role": "system", "content": (
                "Bạn là bộ định tuyến thủ tục hành chính. Chỉ chọn trong danh sách ứng viên. "
                "Không trả lời câu hỏi của người dân. Không tự tạo tên thủ tục. "
                "Nếu chưa đủ rõ để chọn duy nhất một thủ tục, để procedure_name rỗng và needs_clarification=true. "
                "Trả về duy nhất JSON: {\"field\":\"\",\"procedure_name\":\"\",\"confidence\":0.0,\"needs_clarification\":false}."
            )},
            {"role": "user", "content": (
                f"Câu hỏi: {query_text}\n\n"
                f"Lĩnh vực ứng viên: {json.dumps(field_names, ensure_ascii=False)}\n"
                f"Thủ tục ứng viên: {json.dumps(proc_items, ensure_ascii=False)}"
            )},
        ]
        try:
            resp = _call_with_credit_failover(
                pool=openai_client_pool,
                is_credit_error=_is_openai_credit_error,
                operation_name="rag_router_fallback",
                operation=lambda provider_client: provider_client.responses.create(model=RAG_ROUTER_MODEL, input=prompt),
            )
            parsed = _rag_parse_json_object((resp.output_text or "").strip())
        except Exception as e:
            print(f"[RAG] LLM router fallback skipped after error: {type(e).__name__}: {e}")
            return None
        if not parsed:
            return None
        chosen_field = str(parsed.get("field", "") or "").strip()
        chosen_proc = str(parsed.get("procedure_name", "") or "").strip()
        allowed = {(x["field"], x["procedure_name"]): x for x in procedure_candidates[:RAG_LLM_PROCEDURE_CANDIDATES]}
        if chosen_proc:
            matches = [pair for pair in allowed if pair[1] == chosen_proc and (not chosen_field or pair[0] == chosen_field)]
            if not matches:
                chosen_proc = ""
            elif not chosen_field:
                chosen_field = matches[0][0]
        try:
            conf = max(0.0, min(1.0, float(parsed.get("confidence", 0.0) or 0.0)))
        except Exception:
            conf = 0.0
        return {"field": chosen_field, "procedure_name": chosen_proc, "confidence": conf, "needs_clarification": bool(parsed.get("needs_clarification", False))}

    def _route_query(self, query_text: str, qv_norm: np.ndarray, sims: np.ndarray, max_global_similarity: float) -> Tuple[RAGRoute, List[Dict[str, Any]]]:
        route = RAGRoute()
        route.administrative_level = _rag_detect_admin_level(query_text)

        if _rag_is_list_query(query_text):
            route.intents = _rag_detect_section_intents(query_text)
            route.intent = route.intents[0] if route.intents else ""
            route.field, route.field_score = self._field_for_list_query(query_text, qv_norm)
            route.route_method = "list_field_semantic"
            return route, []

        candidates = self._procedure_candidates(query_text, qv_norm, sims, RAG_ROUTE_CANDIDATE_K)
        if not candidates:
            return route, []
        route.candidate_procedures = [x["procedure_name"] for x in candidates[:RAG_LLM_PROCEDURE_CANDIDATES]]
        best = candidates[0]
        second_score = candidates[1]["score"] if len(candidates) > 1 else -1.0
        margin = float(best["score"] - second_score)
        route.procedure_margin = margin

        chosen = best
        should_llm = (
            RAG_ENABLE_LLM_FALLBACK
            and best["lexical_score"] < 0.90
            and (margin < RAG_LLM_FALLBACK_MARGIN or best["score"] < RAG_PROCEDURE_ROUTE_MIN_SCORE)
        )
        if should_llm:
            llm = self._llm_route_fallback(query_text, candidates)
            if llm:
                route.route_method = "global_hybrid+llm_fallback"
                route.needs_clarification = bool(llm.get("needs_clarification", False))
                if llm.get("procedure_name"):
                    for item in candidates[:RAG_LLM_PROCEDURE_CANDIDATES]:
                        if item["procedure_name"] == llm["procedure_name"] and (not llm.get("field") or item["field"] == llm["field"]):
                            chosen = item
                            break
                elif route.needs_clarification:
                    route.clarification_reason = "Có nhiều thủ tục gần nghĩa; cần thêm thông tin để chọn đúng thủ tục."
            else:
                route.route_method = "global_hybrid"
        else:
            route.route_method = "global_hybrid"

        route.field = chosen["field"]
        route.procedure_name = chosen["procedure_name"]
        route.procedure_key = chosen["key"][1]
        route.field_score = float(chosen["score"])
        route.procedure_score = float(chosen["score"])

        # Detect answer sections only after procedure selection so words inside
        # a long procedure title cannot create false intents.
        route.intents = _rag_detect_section_intents(
            query_text,
            procedure_name=route.procedure_name,
        )
        route.intent = route.intents[0] if route.intents else ""

        if not route.needs_clarification and chosen["score"] < RAG_PROCEDURE_ROUTE_MIN_SCORE:
            route.needs_clarification = True
            route.clarification_reason = "Độ phù hợp với các thủ tục trong dữ liệu còn thấp."
        elif not route.needs_clarification and should_llm and margin < RAG_HARD_CLARIFY_MARGIN and route.route_method == "global_hybrid":
            # LLM was unavailable/failed and deterministic candidates are almost tied.
            route.needs_clarification = True
            route.clarification_reason = "Hai thủ tục phù hợp nhất có độ tin cậy quá gần nhau."

        return route, candidates

    def _row_result(self, idx: int, route: RAGRoute, sims: np.ndarray, score_boost: float = 0.0) -> Dict[str, Any]:
        m = self._meta[int(idx)]
        key = self._row_proc_key[int(idx)]
        canonical_name = self._proc_display.get(key, _rag_canonicalize_procedure_name(str(m.get("procedure_name", "") or ""))) if key else ""
        cosine = float(sims[int(idx)])
        return {
            "_index": int(idx), "score": cosine + float(score_boost), "cosine_score": cosine,
            "text": m.get("text", ""), "source": m.get("source", ""), "source_path": m.get("source_path", ""),
            "department": m.get("department", ""), "field": str(m.get("field", "") or "").strip(),
            "administrative_level": str(m.get("administrative_level", "") or "").strip(),
            "procedure_code": m.get("procedure_code", ""), "procedure_name": canonical_name,
            "section_name": str(m.get("section_name", "") or "").strip(),
            "content_type": str(m.get("content_type", "") or "").strip(), "document_title": m.get("document_title", ""),
        }

    def _retrieve_selected_procedure(self, route: RAGRoute, sims: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
        key = (route.field, route.procedure_key)
        indices = self._proc_indices.get(key)
        if indices is None or len(indices) == 0:
            return []
        selected: List[int] = []
        selected_set = set()
        covered_intents = set()

        # Section-first retrieval: guarantee one reliable evidence row for every
        # requested intent when that section exists in the selected procedure.
        for intent in route.intents:
            if intent in covered_intents:
                continue
            section_indices = self._reliable_section_indices.get((key, intent))
            if section_indices is None or len(section_indices) == 0:
                route.missing_intents.append(intent)
                continue
            best_idx = int(section_indices[int(np.argmax(sims[section_indices]))])
            if best_idx not in selected_set:
                selected.append(best_idx)
                selected_set.add(best_idx)
            covered_intents.update(_rag_section_intents_from_name(str(self._meta[best_idx].get("section_name", "") or "")))

        # Fill only from clean anchors of the SAME procedure first.
        anchor_indices = self._proc_anchor_indices.get(key, indices)
        ranked_anchors = sorted(
            [int(i) for i in anchor_indices if int(i) not in selected_set],
            key=lambda i: float(sims[i])
                + (RAG_NEW_SOURCE_TIE_BOOST if str(self._meta[i].get("source_path", "") or "").strip() else 0.0)
                + (RAG_PROCEDURE_SECTION_TIE_BOOST if str(self._meta[i].get("content_type", "") or "") == "procedure_section" else 0.0),
            reverse=True,
        )
        for idx in ranked_anchors:
            if len(selected) >= top_k:
                break
            selected.append(idx)
            selected_set.add(idx)

        if len(selected) < top_k:
            remaining = sorted(
                [int(i) for i in indices if int(i) not in selected_set],
                key=lambda i: float(sims[i]), reverse=True,
            )
            for idx in remaining:
                if len(selected) >= top_k:
                    break
                selected.append(idx)
                selected_set.add(idx)

        rows: List[Dict[str, Any]] = []
        for idx in selected[:top_k]:
            row_intents = _rag_section_intents_from_name(str(self._meta[idx].get("section_name", "") or ""))
            section_boost = RAG_SECTION_SELECTED_BOOST if any(x in route.intents for x in row_intents) else 0.0
            rows.append(self._row_result(idx, route, sims, section_boost))
        return rows

    def retrieve(self, query_text: str, top_k: int = KB_TOP_K, min_sim: float = KB_MIN_SIM) -> RAGRetrievalResult:
        query_text = (query_text or "").strip()
        empty = RAGRetrievalResult(hits=[], route=RAGRoute(), kb_relevant=False, confidence=0.0, low_confidence=False, debug={})
        if not query_text or self._vecs_norm is None or self._vecs is None or self._vecs.shape[0] == 0:
            return empty

        # Exactly one embedding API call, reused for route + retrieval.
        qv = embed_texts([query_text])
        qv_norm = self._normalize_rows(qv)[0]
        sims = (self._vecs_norm @ qv_norm.reshape(-1, 1)).reshape(-1)
        if sims.size == 0:
            return empty
        max_global_similarity = float(np.max(sims))
        route, procedure_candidates = self._route_query(query_text, qv_norm, sims, max_global_similarity)

        field_boosts = _rag_field_soft_keyword_scores(query_text, self._available_fields)
        kb_relevant = bool(field_boosts) or max_global_similarity >= RAG_ADMIN_QUERY_MIN_SIM
        if not kb_relevant:
            print(f"[RAG] Query treated as general conversation | max_sim={max_global_similarity:.3f}")
            return RAGRetrievalResult(hits=[], route=route, kb_relevant=False, confidence=max_global_similarity, low_confidence=False, debug={"max_global_similarity": max_global_similarity})

        hits: List[Dict[str, Any]] = []
        if _rag_is_list_query(query_text) and route.field and route.field in self._field_indices:
            indices = self._field_indices[route.field]
            order = indices[np.argsort(-sims[indices])[:max(1, int(top_k))]]
            hits = [self._row_result(int(i), route, sims) for i in order if float(sims[int(i)]) >= float(min_sim)]
        elif route.procedure_name and route.procedure_key and not route.needs_clarification:
            hits = self._retrieve_selected_procedure(route, sims, max(1, int(top_k)))
        elif route.needs_clarification:
            # Do not mix evidence from competing procedures. Candidate names in
            # route.candidate_procedures are enough for the LLM to ask one question.
            hits = []

        confidence = float(route.procedure_score if route.procedure_score > 0 else max_global_similarity)
        low_confidence = (
            (not hits and not route.needs_clarification and not _rag_is_list_query(query_text))
            or confidence < RAG_FINAL_CONFIDENCE_MIN
            or bool(route.missing_intents)
        )
        if low_confidence and not route.needs_clarification and not _rag_is_list_query(query_text) and not route.missing_intents:
            route.needs_clarification = True
            route.clarification_reason = "Dữ liệu truy hồi chưa đủ chắc chắn để trả lời chính xác."
            hits = []

        print(
            "[RAG V12.2] "
            f"field={route.field or '-'} | procedure={route.procedure_name or '-'} | "
            f"intents={','.join(route.intents) if route.intents else '-'} | "
            f"margin={route.procedure_margin:.3f} | method={route.route_method or '-'} | "
            f"hits={len(hits)} | missing={','.join(route.missing_intents) if route.missing_intents else '-'} | "
            f"clarify={route.needs_clarification}"
        )

        clean_hits: List[Dict[str, Any]] = []
        for row in hits:
            clean = dict(row)
            clean.pop("_index", None)
            clean_hits.append(clean)
        return RAGRetrievalResult(
            hits=clean_hits, route=route, kb_relevant=True, confidence=confidence,
            low_confidence=low_confidence,
            debug={
                "max_global_similarity": max_global_similarity,
                "route_method": route.route_method,
                "procedure_margin": route.procedure_margin,
                "procedure_candidates": [
                    {"field": x["field"], "procedure_name": x["procedure_name"], "score": x["score"]}
                    for x in procedure_candidates[:RAG_LLM_PROCEDURE_CANDIDATES]
                ],
            },
        )

    def query(self, query_text: str, top_k: int = KB_TOP_K, min_sim: float = KB_MIN_SIM) -> List[Dict[str, Any]]:
        return self.retrieve(query_text=query_text, top_k=top_k, min_sim=min_sim).hits


# ============================================================
# CONVERSATION MEMORY (A/B/C)
# ============================================================
def _safe_read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_write_json(path: Path, obj: Any) -> None:
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    # Playback and response threads can persist near-simultaneously: each writer
    # owns a unique temp file; readers never see a partially written JSON file.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as f:
            temp_name = f.name
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


class ConversationMemory:
    """
    Stores:
    - turns: list of {"role": "user"|"assistant", "text": str, "ts": str}
    - summary: str
    - facts: list[str]
    """

    def __init__(self, session_id: str, mem_dir: Path):
        self.session_id = session_id
        self.mem_path = mem_dir / f"session_{session_id}.json"

        state = _safe_read_json(self.mem_path, default={})
        self.turns: List[Dict[str, str]] = state.get("turns", [])
        self.summary: str = state.get("summary", "") or ""
        self.facts: List[str] = state.get("facts", []) or []
        self.dialogue_v17 = state.get("dialogue_v17")
        self.turn_count_since_summary: int = int(state.get("turn_count_since_summary", 0) or 0)

    def save(self) -> None:
        _safe_write_json(
            self.mem_path,
            {
                "session_id": self.session_id,
                "turns": self.turns,
                "summary": self.summary,
                "facts": self.facts,
                "dialogue_v17": self.dialogue_v17,
                "turn_count_since_summary": self.turn_count_since_summary,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    def add_turn(self, role: str, text: str) -> None:
        self.turns.append(
            {
                "role": role,
                "text": text,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        if role == "assistant":
            self.turn_count_since_summary += 1

    def get_window(self, window_turns: int = WINDOW_TURNS) -> List[Dict[str, str]]:
        return self.turns[-max(0, window_turns * 2):]

    def maybe_update_summary_and_facts(self) -> None:
        # V17 maintains its own compact state without a second summary model.
        return


# ============================================================
# SESSION HELPERS
# ============================================================
def _ts_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _session_id_now() -> str:
    """
    Return a timestamp-based ID with millisecond suffix.

    V8 fix:
    - The old version used seconds only: YYYYmmdd_HHMMSS.
    - If a person disappeared/reappeared quickly, a new session could be created
      inside the same second and reuse the same session_id.
    - That could also make greeting logic think the new session was already greeted.
    """
    return time.strftime("%Y%m%d_%H%M%S") + f"_{int((time.time() % 1.0) * 1000):03d}"


def _sanitize_text_for_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", text)


def save_memory_snapshot(memory: ConversationMemory, out_path: Path) -> None:
    snapshot = {
        "session_id": memory.session_id,
        "summary": memory.summary,
        "facts": memory.facts,
        "window": memory.get_window(window_turns=WINDOW_TURNS),
        "saved_at": _ts_now(),
    }
    _safe_write_json(out_path, snapshot)


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


class RuntimeSessionManager:
    def __init__(self, sessions_root_dir: Path):
        self.sessions_root_dir = sessions_root_dir
        self.sessions_root_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.active_session: Optional[SessionContext] = None
        # Incremented every time the active session is created or closed.
        # The main loop uses this to interrupt microphone recording if person
        # detection changes the session while recording is waiting/blocking.
        self.session_generation: int = 0

    def _write_session_meta_locked(self, session: SessionContext) -> None:
        data = {
            "session_id": session.session_id,
            "started_at": session.started_ts,
            "ended_at": session.ended_ts,
            "end_reason": session.end_reason,
            "turn_count": session.turn_counter,
            "greeting_played": session.greeting_played,
            "session_dir": str(session.session_dir),
            "memory_file": str(session.memory.mem_path),
            "updated_at": _ts_now(),
        }
        _safe_write_json(session.meta_path, data)

    def _create_new_session_locked(self, trigger: str) -> SessionContext:
        session_id = _session_id_now()
        session_dir = self.sessions_root_dir / session_id
        memory_dir = session_dir / "memory"
        turns_dir = session_dir / "turns"
        logs_dir = session_dir / "logs"

        memory_dir.mkdir(parents=True, exist_ok=True)
        turns_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        memory = ConversationMemory(session_id=session_id, mem_dir=memory_dir)
        memory.save()

        session = SessionContext(
            session_id=session_id,
            session_dir=session_dir,
            memory_dir=memory_dir,
            turns_dir=turns_dir,
            logs_dir=logs_dir,
            meta_path=session_dir / "meta.json",
            memory=memory,
            started_ts=_ts_now(),
            started_monotonic=time.monotonic(),
        )
        self.active_session = session
        self.session_generation += 1
        self._write_session_meta_locked(session)
        append_jsonl(
            logs_dir / "events.jsonl",
            {
                "ts": _ts_now(),
                "event": "session_created",
                "trigger": trigger,
                "session_id": session.session_id,
            },
        )
        print(f"[SESSION] Created new session: {session.session_id}")
        return session

    def _close_session_locked(self, reason: str) -> Optional[SessionContext]:
        session = self.active_session
        if session is None:
            return None

        session.ended_ts = _ts_now()
        session.end_reason = reason
        try:
            session.memory.save()
        except Exception:
            pass

        self._write_session_meta_locked(session)
        append_jsonl(
            session.logs_dir / "events.jsonl",
            {
                "ts": _ts_now(),
                "event": "session_closed",
                "reason": reason,
                "session_id": session.session_id,
            },
        )
        self.active_session = None
        self.session_generation += 1
        print(f"[SESSION] Closed session: {session.session_id} | reason={reason}")
        return session

    def handle_person_state_change(self, person_present: bool, reason: str) -> None:
        with self.lock:
            if person_present:
                if self.active_session is None:
                    self._create_new_session_locked(trigger=f"person_present_true | {reason}")
            else:
                if self.active_session is not None:
                    self._close_session_locked(reason=f"person_present_false | {reason}")

    def claim_greeting_for_active_session(self) -> Optional[SessionContext]:
        """
        Thread-safe greeting gate.

        A new session is created by the person-detection thread, but greeting audio
        is played by the main thread. This method marks the active session as
        already-greeted before playback starts so greeting is played exactly once
        per SessionContext, even if the main loop checks the session repeatedly.
        """
        with self.lock:
            session = self.active_session
            if session is None:
                return None
            if session.greeting_played:
                return None

            session.greeting_played = True
            self._write_session_meta_locked(session)
            append_jsonl(
                session.logs_dir / "events.jsonl",
                {
                    "ts": _ts_now(),
                    "event": "greeting_claimed",
                    "session_id": session.session_id,
                },
            )
            return session

    def has_active_session(self) -> bool:
        with self.lock:
            return self.active_session is not None

    def get_active_session(self) -> Optional[SessionContext]:
        with self.lock:
            return self.active_session

    def get_session_generation(self) -> int:
        with self.lock:
            return self.session_generation

    def has_session_changed_since(self, generation: int) -> bool:
        with self.lock:
            return self.session_generation != generation

    def create_turn_for_active_session(self) -> Optional[Tuple[SessionContext, TurnContext]]:
        with self.lock:
            session = self.active_session
            if session is None:
                return None

            session.turn_counter += 1
            turn_index = session.turn_counter
            turn_stamp = _session_id_now()
            turn_id = f"turn_{turn_index:03d}_{turn_stamp}"
            turn_dir = session.turns_dir / turn_id
            audio_in_dir = turn_dir / "audio_in"
            audio_out_dir = turn_dir / "audio_out"
            transcripts_dir = turn_dir / "transcripts"
            motions_dir = turn_dir / "motions"
            logs_dir = turn_dir / "logs"

            for p in (audio_in_dir, audio_out_dir, transcripts_dir, motions_dir, logs_dir):
                p.mkdir(parents=True, exist_ok=True)

            wav_prefix = f"{turn_id}_assistant"
            turn = TurnContext(
                turn_index=turn_index,
                turn_id=turn_id,
                turn_dir=turn_dir,
                audio_in_dir=audio_in_dir,
                audio_out_dir=audio_out_dir,
                transcripts_dir=transcripts_dir,
                motions_dir=motions_dir,
                logs_dir=logs_dir,
                wav_in_path=audio_in_dir / f"{turn_id}_user.wav",
                user_transcript_path=transcripts_dir / "user_transcript.txt",
                assistant_response_path=transcripts_dir / "assistant_full_response.txt",
                memory_before_path=transcripts_dir / "memory_before.json",
                memory_after_path=transcripts_dir / "memory_after.json",
                turn_meta_path=turn_dir / "meta.json",
                wav_prefix=wav_prefix,
                started_ts=_ts_now(),
            )

            self._write_session_meta_locked(session)
            append_jsonl(
                session.logs_dir / "events.jsonl",
                {
                    "ts": _ts_now(),
                    "event": "turn_created",
                    "session_id": session.session_id,
                    "turn_id": turn.turn_id,
                    "turn_index": turn.turn_index,
                },
            )
            return session, turn

    def finalize_turn(
        self,
        session: SessionContext,
        turn: TurnContext,
        status: str,
        user_text: str = "",
        assistant_text: str = "",
        error: str = "",
    ) -> None:
        data = {
            "session_id": session.session_id,
            "turn_id": turn.turn_id,
            "turn_index": turn.turn_index,
            "started_at": turn.started_ts,
            "ended_at": _ts_now(),
            "status": status,
            "user_text": user_text,
            "assistant_text": assistant_text,
            "error": error,
            "paths": {
                "turn_dir": str(turn.turn_dir),
                "wav_in": str(turn.wav_in_path),
                "user_transcript": str(turn.user_transcript_path),
                "assistant_response": str(turn.assistant_response_path),
                "audio_out_dir": str(turn.audio_out_dir),
                "motions_dir": str(turn.motions_dir),
                "memory_before": str(turn.memory_before_path),
                "memory_after": str(turn.memory_after_path),
            },
        }
        _safe_write_json(turn.turn_meta_path, data)
        append_jsonl(
            session.logs_dir / "events.jsonl",
            {
                "ts": _ts_now(),
                "event": "turn_finished",
                "session_id": session.session_id,
                "turn_id": turn.turn_id,
                "status": status,
                "error": error,
            },
        )
        with self.lock:
            self._write_session_meta_locked(session)

    def shutdown(self, reason: str = "runtime_shutdown") -> None:
        with self.lock:
            if self.active_session is not None:
                self._close_session_locked(reason=reason)


class UnityPersonStateDispatcher:
    """
    Delay person_detection packets to Unity while audio/motion playback is active.

    Internal Python logic may still react immediately to person_present changes.
    Only the Unity-facing update is deferred until playback becomes idle.
    """

    def __init__(self, tcp: UnityTcpServer, enabled: bool = True):
        self.tcp = tcp
        self.enabled = enabled
        self.lock = threading.Lock()
        self.playback_busy = False
        self.last_sent_payload: Optional[Dict[str, Any]] = None
        self.pending_payload: Optional[Dict[str, Any]] = None

    def set_playback_busy(self, is_busy: bool) -> None:
        payload_to_send: Optional[Dict[str, Any]] = None
        with self.lock:
            self.playback_busy = is_busy
            if (not self.playback_busy) and self.pending_payload is not None:
                payload_to_send = self.pending_payload
                self.pending_payload = None

        if payload_to_send is not None:
            self._send_payload(payload_to_send)

    def publish_or_defer(
        self,
        person_present: bool,
        face_valid: bool,
        pose_valid: bool,
        consecutive_hits: int,
        consecutive_misses: int,
        reason: str,
        bbox: Tuple[int, int, int, int],
        center: Tuple[int, int],
    ) -> None:
        if not self.enabled:
            return

        payload = {
            'person_detected': person_present,
            'person_id': 1 if person_present else -1,
            'person_name': 'person' if person_present else '',
            'confidence': 1.0 if (face_valid or pose_valid) else 0.0,
            'bbox_x': bbox[0],
            'bbox_y': bbox[1],
            'bbox_w': bbox[2],
            'bbox_h': bbox[3],
            'center_x': center[0],
            'center_y': center[1],
            'meta': {
                'face_valid': face_valid,
                'pose_valid': pose_valid,
                'hits': consecutive_hits,
                'misses': consecutive_misses,
                'reason': reason,
            },
        }

        should_send_now = False
        with self.lock:
            if self.playback_busy:
                self.pending_payload = payload
                return

            if self._payload_equals(self.last_sent_payload, payload):
                return

            self.last_sent_payload = copy.deepcopy(payload)
            should_send_now = True

        if should_send_now:
            self._send_payload(payload)

    def flush_pending(self) -> None:
        payload_to_send: Optional[Dict[str, Any]] = None
        with self.lock:
            if self.playback_busy:
                return
            if self.pending_payload is not None:
                payload_to_send = self.pending_payload
                self.pending_payload = None

        if payload_to_send is not None:
            self._send_payload(payload_to_send)

    def _send_payload(self, payload: Dict[str, Any]) -> None:
        try:
            self.tcp.send_person_detection(**payload)
            with self.lock:
                self.last_sent_payload = copy.deepcopy(payload)
        except Exception as e:
            print(f'[PERSON] Failed to send detection result: {type(e).__name__}: {e}')

    @staticmethod
    def _payload_equals(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> bool:
        if a is None or b is None:
            return False
        return a == b


class UnityMicrophoneStateDispatcher:
    """
    Send microphone ON/OFF state to Unity.

    Meaning:
    - mic_on=True:
        Python is ready to listen/record user speech.
    - mic_on=False:
        Python should not accept microphone input because it is playing audio,
        processing, waiting, or shutting down.

    This dispatcher avoids sending duplicate consecutive states.
    It requires unity_tcp_sender_v7.UnityTcpServer.send_microphone_state(...).
    """

    def __init__(self, tcp: UnityTcpServer, enabled: bool = True):
        self.tcp = tcp
        self.enabled = enabled
        self.lock = threading.Lock()
        self.last_mic_on: Optional[bool] = None
        self.last_reason: str = ""
        self.last_session_id: str = ""
        self.last_turn_id: str = ""

    def set_mic_state(
        self,
        mic_on: bool,
        reason: str = "",
        session_id: str = "",
        turn_id: str = "",
        force: bool = False,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return

        mic_on = bool(mic_on)
        reason = str(reason)
        session_id = str(session_id)
        turn_id = str(turn_id)

        with self.lock:
            if (
                not force
                and self.last_mic_on == mic_on
                and self.last_reason == reason
                and self.last_session_id == session_id
                and self.last_turn_id == turn_id
            ):
                return

            self.last_mic_on = mic_on
            self.last_reason = reason
            self.last_session_id = session_id
            self.last_turn_id = turn_id

        try:
            self.tcp.send_microphone_state(
                mic_on=mic_on,
                reason=reason,
                session_id=session_id,
                turn_id=turn_id,
                meta=meta if meta is not None else {},
            )
            print(f"[MIC] {'ON' if mic_on else 'OFF'} | reason={reason} | session={session_id} | turn={turn_id}")
        except Exception as e:
            print(f"[MIC] Failed to send microphone_state: {type(e).__name__}: {e}")


class ActiveTurnAbortController:
    """
    Thread-safe controller for aborting the current assistant response when
    person detection reports that the user has left.

    Important behavior:
    - It does not stop playback immediately.
    - It only requests the response pipeline to stop after the current spoken
      sentence/audio job finishes.
    - This prevents cutting audio and motion in the middle of one sentence.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.active_session_id: str = ""
        self.active_turn_id: str = ""
        self.response_abort_event: Optional[threading.Event] = None
        self.abort_reason: str = ""

    def start_turn(
        self,
        session_id: str,
        turn_id: str,
        response_abort_event: threading.Event,
    ) -> None:
        with self.lock:
            self.active_session_id = str(session_id)
            self.active_turn_id = str(turn_id)
            self.response_abort_event = response_abort_event
            self.abort_reason = ""

    def clear_turn(self, turn_id: str = "") -> None:
        with self.lock:
            if turn_id and self.active_turn_id and turn_id != self.active_turn_id:
                return
            self.active_session_id = ""
            self.active_turn_id = ""
            self.response_abort_event = None
            self.abort_reason = ""

    def request_abort(self, reason: str = "person_left") -> bool:
        with self.lock:
            ev = self.response_abort_event
            if ev is None:
                return False

            if not ev.is_set():
                self.abort_reason = str(reason)
                ev.set()
                print(
                    f"[ABORT] Response abort requested | "
                    f"session={self.active_session_id} | "
                    f"turn={self.active_turn_id} | reason={self.abort_reason}"
                )
                return True

            return False

    def get_abort_reason(self) -> str:
        with self.lock:
            return self.abort_reason


# ============================================================
# STREAMING + SENTENCE SPLIT
# ============================================================
_SENT_END_RE = re.compile(r"(.+?)([\.!\?…]+|\n+)(\s+|$)", re.DOTALL)


def _extract_complete_sentences(buffer: str) -> Tuple[List[str], str]:
    """
    Split buffer into (completed_sentences, remainder).
    """
    sentences: List[str] = []
    i = 0

    while True:
        m = _SENT_END_RE.match(buffer[i:])
        if not m:
            break
        sent = (m.group(1) + m.group(2)).strip()
        if sent:
            sentences.append(sent)
        i += m.end()

    return sentences, buffer[i:]


def _build_system_prompt() -> str:
    """
    Load voice-first constraints and RAG grounding from an external UTF-8 file.

    The file is read for every response so its content can be adjusted without
    rebuilding or restarting the runtime.
    """
    if not SYSTEM_PROMPT_FILE.is_file():
        raise RuntimeError(
            f"Missing system prompt file: {SYSTEM_PROMPT_FILE}. "
            "Create system_prompt.txt beside the running .py/.exe."
        )

    try:
        prompt = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8-sig")
    except Exception as e:
        raise RuntimeError(
            f"Cannot read system prompt file {SYSTEM_PROMPT_FILE}: "
            f"{type(e).__name__}: {e}"
        ) from e

    if not prompt.strip():
        raise RuntimeError(
            f"System prompt file is empty: {SYSTEM_PROMPT_FILE}"
        )

    return prompt


def _format_memory_section(summary: str, facts: List[str]) -> str:
    facts_txt = ""
    if facts:
        facts_txt = "\n".join([f"- {f}" for f in facts])
    return (
        "=== MEMORY SUMMARY (may be empty) ===\n"
        f"{summary.strip()}\n\n"
        "=== LONG-TERM FACTS (may be empty) ===\n"
        f"{facts_txt}\n"
    ).strip()


def _format_kb_section(
    retrieval: RAGRetrievalResult,
) -> str:
    if not retrieval.kb_relevant:
        return ""

    route = retrieval.route
    lines = [
        "=== KNOWLEDGE BASE (retrieved) ===",
        (
            "RETRIEVAL STATUS: "
            f"field={route.field or 'unknown'}; "
            f"procedure={route.procedure_name or 'unknown'}; "
            f"administrative_level={route.administrative_level or 'unknown'}; "
            f"intents={','.join(route.intents) if route.intents else 'general'}; "
            f"missing_intents={','.join(route.missing_intents) if route.missing_intents else 'none'}; "
            f"NEEDS_CLARIFICATION={'true' if route.needs_clarification else 'false'}"
        ),
    ]

    if route.needs_clarification and route.clarification_reason:
        lines.append(
            f"CLARIFICATION REASON: {route.clarification_reason}"
        )

    if route.needs_clarification and route.candidate_procedures:
        lines.append(
            "CANDIDATE PROCEDURES: " + " | ".join(route.candidate_procedures[:5])
        )

    if retrieval.low_confidence:
        lines.append(
            "RETRIEVAL CONFIDENCE: LOW. "
            "Do not guess missing administrative facts."
        )

    if not retrieval.hits:
        lines.append(
            "NO RELIABLE KB CHUNK WAS RETRIEVED. "
            "Do not invent administrative-procedure details."
        )
        return "\n".join(lines).strip()

    for i, h in enumerate(retrieval.hits, 1):
        src = str(h.get("source", "") or "")
        source_path = str(h.get("source_path", "") or "")
        department = str(h.get("department", "") or "")
        field_name = str(h.get("field", "") or "")
        procedure_name = str(h.get("procedure_name", "") or "")
        procedure_code = str(h.get("procedure_code", "") or "")
        admin_level = str(h.get("administrative_level", "") or "")
        section_name = str(h.get("section_name", "") or "")
        txt = (h.get("text", "") or "").strip()

        score = float(h.get("score", 0.0) or 0.0)
        cosine_score = float(
            h.get("cosine_score", 0.0) or 0.0
        )

        metadata_parts = [
            f"source={src}",
            f"department={department}",
            f"field={field_name}",
            f"procedure={procedure_name}",
            f"procedure_code={procedure_code}",
            f"level={admin_level}",
            f"section={section_name}",
        ]

        if source_path:
            metadata_parts.append(
                f"source_path={source_path}"
            )

        lines.append(
            f"[{i}] ({'; '.join(metadata_parts)})\n{txt}"
        )

    return "\n".join(lines).strip()


def llm_stream_to_tts_queue(
    user_text: str, tts_queue: queue.Queue, stop_event: threading.Event,
    memory: ConversationMemory, kb_store: KnowledgeBase,
    response_abort_event: Optional[threading.Event] = None,
    delivery_token: Optional[dict] = None,
    send_panel=None, turn_id="",
) -> str:
    """V17 model-only: display information independently of speech."""
    if not hasattr(memory, "_v17_bridge"):
        def create(**kwargs):
            return _call_with_credit_failover(
                pool=openai_client_pool, is_credit_error=_is_openai_credit_error,
                operation_name="case_rag_v17",
                operation=lambda client: client.with_options(timeout=90.0, max_retries=0).responses.create(**kwargs),
            )
        memory._v17_bridge = VoiceBridge(
            kb_store, create, memory, model=V17_CONFIG.get("model", LLM_MODEL),
            enabled=V17_CONFIG.get("enable_live_api", False),
        )
    return memory._v17_bridge.generate(
        user_text, tts_queue, stop_event, response_abort_event,
        _extract_complete_sentences, delivery_token if delivery_token is not None else {},
        send_panel=send_panel, turn_id=turn_id,
    )


# ============================================================
# PERSON DETECTION HELPERS
# ============================================================
def clamp(val: int, vmin: int, vmax: int) -> int:
    return max(vmin, min(val, vmax))


def point_in_roi(x: float, y: float, roi: Tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = roi
    return (x1 <= x <= x2) and (y1 <= y <= y2)


def box_center(x: int, y: int, w: int, h: int) -> Tuple[float, float]:
    return x + w / 2.0, y + h / 2.0


def calc_roi(frame_w: int, frame_h: int, cfg: VoiceMotionRuntimeConfig) -> Tuple[int, int, int, int]:
    x1 = int(frame_w * cfg.person_roi_x_min_ratio)
    x2 = int(frame_w * cfg.person_roi_x_max_ratio)
    y1 = int(frame_h * cfg.person_roi_y_min_ratio)
    y2 = int(frame_h * cfg.person_roi_y_max_ratio)
    return (x1, y1, x2, y2)


def detect_face(
    frame_bgr: np.ndarray,
    roi: Tuple[int, int, int, int],
    face_detector: Any,
    cfg: VoiceMotionRuntimeConfig,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Return:
        valid: bool
        info: dict
    """
    frame_h, frame_w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = face_detector.process(rgb)

    best_info = {
        "valid": False,
        "bbox": None,
        "center": None,
        "reason": "No face",
    }

    if not results.detections:
        return False, best_info

    for det in results.detections:
        bbox = det.location_data.relative_bounding_box

        x = int(bbox.xmin * frame_w)
        y = int(bbox.ymin * frame_h)
        w = int(bbox.width * frame_w)
        h = int(bbox.height * frame_h)

        x = clamp(x, 0, frame_w - 1)
        y = clamp(y, 0, frame_h - 1)
        w = max(1, min(w, frame_w - x))
        h = max(1, min(h, frame_h - y))

        cx, cy = box_center(x, y, w, h)

        size_ok = (w >= frame_w * cfg.person_min_face_box_w_ratio) and (
            h >= frame_h * cfg.person_min_face_box_h_ratio
        )
        roi_ok = point_in_roi(cx, cy, roi)
        valid = size_ok and roi_ok

        best_info = {
            "valid": valid,
            "bbox": (x, y, w, h),
            "center": (int(cx), int(cy)),
            "reason": f"Face detected | size_ok={size_ok}, roi_ok={roi_ok}",
        }

        if valid:
            return True, best_info

    return False, best_info


def get_landmark_xy(
    landmarks: Any,
    idx: int,
    frame_w: int,
    frame_h: int,
    vis_thresh: float = 0.5,
) -> Optional[Tuple[int, int]]:
    lm = landmarks[idx]
    if lm.visibility < vis_thresh:
        return None
    x = int(lm.x * frame_w)
    y = int(lm.y * frame_h)
    return (x, y)


def detect_pose(
    frame_bgr: np.ndarray,
    roi: Tuple[int, int, int, int],
    pose_detector: Any,
    cfg: VoiceMotionRuntimeConfig,
    mp_pose_module: Any,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Pose hợp lệ nếu:
    - có đủ mốc vai trái + vai phải
    - tâm 2 vai nằm trong ROI
    - khoảng cách 2 vai đủ lớn
    """
    frame_h, frame_w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = pose_detector.process(rgb)

    info = {
        "valid": False,
        "landmarks": None,
        "shoulder_center": None,
        "shoulder_width": None,
        "reason": "No pose",
    }

    if not results.pose_landmarks:
        return False, info

    landmarks = results.pose_landmarks.landmark

    left_shoulder = get_landmark_xy(
        landmarks,
        mp_pose_module.PoseLandmark.LEFT_SHOULDER.value,
        frame_w,
        frame_h,
    )
    right_shoulder = get_landmark_xy(
        landmarks,
        mp_pose_module.PoseLandmark.RIGHT_SHOULDER.value,
        frame_w,
        frame_h,
    )

    if left_shoulder is None or right_shoulder is None:
        info["reason"] = "Pose detected but shoulders not reliable"
        return False, info

    sx = int((left_shoulder[0] + right_shoulder[0]) / 2)
    sy = int((left_shoulder[1] + right_shoulder[1]) / 2)

    shoulder_width = math.dist(left_shoulder, right_shoulder)
    shoulder_width_ratio = shoulder_width / float(frame_w)

    roi_ok = point_in_roi(sx, sy, roi)
    size_ok = shoulder_width_ratio >= cfg.person_min_shoulder_width_ratio

    valid = roi_ok and size_ok

    info = {
        "valid": valid,
        "landmarks": results.pose_landmarks,
        "shoulder_center": (sx, sy),
        "shoulder_width": shoulder_width,
        "reason": f"Pose detected | size_ok={size_ok}, roi_ok={roi_ok}",
    }

    return valid, info


def save_person_session_event_image(
    frame_bgr: np.ndarray,
    session: Optional[SessionContext],
    event_name: str,
    state: PersonDetectionState,
    roi: Tuple[int, int, int, int],
    face_info: Optional[Dict[str, Any]] = None,
    pose_info: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    """
    Save the exact rotated portrait frame used by V13.2 vision when a session
    starts or closes. Diagnostic overlays are added only to the saved copy.
    """
    if session is None:
        return None

    try:
        event_dir = session.session_dir / "person_detection_events"
        event_dir.mkdir(parents=True, exist_ok=True)

        event_path = event_dir / f"session_{event_name}_{_session_id_now()}.jpg"
        debug_frame = frame_bgr.copy()
        frame_h, frame_w = debug_frame.shape[:2]

        x1_roi, y1_roi, x2_roi, y2_roi = roi
        cv2.rectangle(
            debug_frame,
            (x1_roi, y1_roi),
            (min(x2_roi, frame_w - 1), min(y2_roi, frame_h - 1)),
            (0, 255, 255),
            3,
        )

        face_bbox = (
            face_info.get("bbox")
            if face_info is not None and face_info.get("bbox") is not None
            else state.last_face_bbox
        )
        if face_bbox is not None:
            x, y, w, h = face_bbox
            cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (255, 0, 0), 3)

        pose_center = (
            pose_info.get("shoulder_center")
            if pose_info is not None
            else None
        )
        event_center = pose_center or state.last_center
        if event_center is not None:
            cv2.circle(debug_frame, event_center, 8, (0, 255, 255), -1)

        status_text = (
            f"SESSION {event_name.upper()} | "
            f"face={state.last_face_valid} pose={state.last_pose_valid}"
        )
        cv2.putText(
            debug_frame,
            status_text,
            (30, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            (0, 255, 0) if event_name == "start" else (0, 0, 255),
            3,
        )
        cv2.putText(
            debug_frame,
            state.last_reason[:140],
            (30, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
        )

        if not cv2.imwrite(str(event_path), debug_frame):
            print(f"[PERSON] Failed to save session {event_name} image: {event_path}")
            return None

        print(f"[PERSON] Saved session {event_name} image: {event_path}")
        return event_path

    except Exception as e:
        print(
            f"[PERSON] Failed to save session {event_name} image: "
            f"{type(e).__name__}: {e}"
        )
        return None


# ============================================================
# PRESET AUDIO HELPERS
# ============================================================
PRESET_MOTION_REQUIRED_COLUMNS: Tuple[str, ...] = (
    "time_sec",
    "roll",
    "yaw",
    "lip_open_dist_3d",
    "mouth_width_dist_3d",
    "upper_lip_thickness_3d",
    "lower_lip_thickness_3d",
)


def list_audio_files(audio_dir: Path, extensions: Tuple[str, ...] = (".wav", ".wave")) -> List[Path]:
    """
    Return sorted audio files from a folder.
    """
    audio_dir = Path(audio_dir)
    if not audio_dir.exists():
        return []

    exts = tuple(e.lower() for e in extensions)
    files = [p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    return sorted(files)


def choose_random_audio(audio_dir: Path, extensions: Tuple[str, ...] = (".wav", ".wave")) -> Optional[Path]:
    """
    Choose one random audio file from a folder.
    """
    files = list_audio_files(audio_dir, extensions=extensions)
    if not files:
        return None
    return random.choice(files)


def read_preset_text_for_unity(wav_path: Path) -> str:
    """
    Optional display text for a preset WAV.
    If a .txt file with the same stem exists, use its content.
    Otherwise return empty string.
    """
    txt_path = wav_path.with_suffix(".txt")
    if not txt_path.exists():
        return ""
    try:
        return txt_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def get_preset_motion_csv_path(wav_path: Path) -> Path:
    """
    Map a preset WAV to its pre-generated motion CSV in the same folder.

    Examples:
        hello.wav  -> hello.motion.csv
        hello.wave -> hello.motion.csv
    """
    return Path(wav_path).with_suffix(".motion.csv")


def _preset_motion_cache_key(wav_path: Path) -> str:
    """Return a normalized absolute key for one preset WAV."""
    return os.path.normcase(str(Path(wav_path).resolve()))


def validate_preset_motion_dataframe(
    df_motion: pd.DataFrame,
    wav_path: Path,
    motion_csv_path: Path,
) -> None:
    """Validate a prepared motion CSV against the current Unity sender contract."""
    if df_motion.empty:
        raise RuntimeError(f"Preset motion CSV has no rows: {motion_csv_path}")

    missing_columns = [
        column
        for column in PRESET_MOTION_REQUIRED_COLUMNS
        if column not in df_motion.columns
    ]
    if missing_columns:
        raise KeyError(
            f"Preset motion CSV for '{wav_path.name}' is missing columns "
            f"{missing_columns}: {motion_csv_path}"
        )

    try:
        required_values = df_motion.loc[
            :, PRESET_MOTION_REQUIRED_COLUMNS
        ].to_numpy(dtype=np.float64)
    except Exception as e:
        raise RuntimeError(
            f"Preset motion CSV contains non-numeric Unity values: "
            f"{motion_csv_path} | {type(e).__name__}: {e}"
        ) from e

    if not np.isfinite(required_values).all():
        raise RuntimeError(
            f"Preset motion CSV contains NaN or Inf in Unity columns: "
            f"{motion_csv_path}"
        )

    for lip_column in PRESET_MOTION_REQUIRED_COLUMNS[3:]:
        values = df_motion[lip_column].to_numpy(dtype=np.float64)
        if np.any(values < 0.0) or np.any(values > 1.0):
            raise RuntimeError(
                f"Preset motion column '{lip_column}' is outside [0, 1]: "
                f"{motion_csv_path}"
            )


def load_preset_motion_cache(
    audio_dirs: Tuple[Path, ...],
    extensions: Tuple[str, ...] = (".wav", ".wave"),
) -> Dict[str, pd.DataFrame]:
    """
    Load all prepared greeting/waiting motion CSV files into RAM once.

    A preset WAV must have a same-stem .motion.csv beside it. Missing or invalid
    motion is treated as a startup configuration error. This function never
    runs feature extraction or motion inference.
    """
    cache: Dict[str, pd.DataFrame] = {}

    for audio_dir in audio_dirs:
        wav_files = list_audio_files(audio_dir, extensions=extensions)
        print(f"[PRESET CACHE] Scan {audio_dir} -> {len(wav_files)} WAV file(s)")

        for wav_path in wav_files:
            motion_csv_path = get_preset_motion_csv_path(wav_path)
            if not motion_csv_path.exists():
                raise FileNotFoundError(
                    f"Prepared preset motion is missing for: {wav_path}\n"
                    f"Expected: {motion_csv_path}\n"
                    "Run generate_preset_motion_v1.py before starting the runtime."
                )

            try:
                df_motion = pd.read_csv(
                    motion_csv_path,
                    encoding="utf-8-sig",
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to read preset motion CSV: {motion_csv_path} | "
                    f"{type(e).__name__}: {e}"
                ) from e

            validate_preset_motion_dataframe(
                df_motion=df_motion,
                wav_path=wav_path,
                motion_csv_path=motion_csv_path,
            )

            cache_key = _preset_motion_cache_key(wav_path)
            cache[cache_key] = df_motion
            print(
                f"[PRESET CACHE] Loaded {wav_path.name} -> "
                f"{motion_csv_path.name} ({len(df_motion)} frames)"
            )

    print(f"[PRESET CACHE] Ready: {len(cache)} preset motion file(s) in RAM")
    return cache


def get_cached_preset_motion(
    wav_path: Path,
    preset_motion_cache: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Return the prepared motion already loaded in RAM for one preset WAV."""
    cache_key = _preset_motion_cache_key(wav_path)
    if cache_key not in preset_motion_cache:
        expected_path = get_preset_motion_csv_path(wav_path)
        raise KeyError(
            f"Preset motion is not loaded in RAM for: {wav_path}. "
            f"Expected CSV: {expected_path}"
        )
    return preset_motion_cache[cache_key]


def run_existing_wav_with_motion(
    wav_path: Path,
    preset_name: str,
    job_id: int,
    motion_cfg: MotionRuntimeConfig,
    runtime_cfg: VoiceMotionRuntimeConfig,
    tcp: UnityTcpServer,
    unity_person_dispatcher: UnityPersonStateDispatcher,
    preset_motion_cache: Dict[str, pd.DataFrame],
    save_dir: Optional[Path] = None,
    display_text: str = "",
) -> bool:
    """
    Run an existing WAV through the same Unity-facing playback stage:
    - optionally send speech_text to Unity
    - get its prepared motion from the RAM cache
    - play WAV and send motion in sync

    This function does not call OpenAI, ElevenLabs, feature extraction, or
    motion inference.
    """
    wav_path = Path(wav_path)
    if not wav_path.exists():
        print(f"[PRESET] WAV not found: {wav_path}")
        return False

    preset_motion_cfg = copy.deepcopy(motion_cfg)
    if save_dir is not None:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        preset_motion_cfg.save_dir = str(save_dir)

    print(f"[PRESET] Start {preset_name}: {wav_path}")
    unity_person_dispatcher.set_playback_busy(True)

    try:
        if runtime_cfg.send_preset_speech_text_to_unity and display_text.strip():
            try:
                tcp.send_speech_text(text=display_text.strip(), job_id=job_id)
                print(f"[PRESET] Sent speech_text for {preset_name}")
            except Exception as e:
                print(f"[PRESET] Failed to send speech_text for {preset_name}: {type(e).__name__}: {e}")

        try:
            df_send = get_cached_preset_motion(
                wav_path=wav_path,
                preset_motion_cache=preset_motion_cache,
            )
            send_prebuilt_motion_in_sync(
                df_send=df_send,
                wav_path=wav_path,
                tcp=tcp,
                cfg=preset_motion_cfg,
            )
            print(f"[PRESET] Finished {preset_name} with motion")
            return True
        except Exception as e:
            print(f"[PRESET] Cached motion/playback failed for {preset_name}: {type(e).__name__}: {e}")
            if runtime_cfg.play_audio_even_if_motion_failed:
                print(f"[PRESET] Fallback audio-only playback for {preset_name}")
                play_wav_only(wav_path, tail_pad_ms=TAIL_PAD_MS)
                print(f"[PRESET] Finished {preset_name} audio-only")
                return True
            return False

    finally:
        unity_person_dispatcher.set_playback_busy(False)
        unity_person_dispatcher.flush_pending()


# ============================================================
# THREAD WORKERS
# ============================================================
SENTINEL = None


def tts_worker_v2(
    tts_queue: queue.Queue,
    motion_build_queue: queue.Queue,
    playback_queue: queue.Queue,
    stop_event: threading.Event,
    wav_prefix: str,
    audio_out_dir: Path,
    response_abort_event: Optional[threading.Event] = None,
    delivery_token: Optional[dict] = None,
) -> None:
    """
    Thread 1:
    Receives (job_id, sentence) -> generates WAV -> pushes AudioJob into:
    - motion_build_queue
    - playback_queue
    """
    while not stop_event.is_set():
        try:
            item = tts_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if item is SENTINEL:
            tts_queue.task_done()
            motion_build_queue.put(SENTINEL)
            playback_queue.put(SENTINEL)
            break

        job_id, sentence = item
        sentence = str(sentence).strip()

        if response_abort_event is not None and response_abort_event.is_set():
            # User has left. Do not generate TTS for queued future sentences.
            # The playback worker will finish only the sentence already being played.
            print(f"[ABORT] Skip queued TTS job {job_id} because person left.")
            tts_queue.task_done()
            continue

        if not sentence:
            tts_queue.task_done()
            continue

        wav_out = audio_out_dir / f"{wav_prefix}_sent_{int(job_id):03d}.wav"

        try:
            print(f"\n\n🗣️ [TTS queued #{job_id}] {sentence}\n", flush=True)
            text_to_speech(sentence, wav_out)
            wait_file_stable(wav_out)
            if delivery_token is not None:
                delivery_token["tts_ready"] = True
                delivery_token["audio_file"] = str(wav_out)

            if response_abort_event is not None and response_abort_event.is_set():
                print(f"[ABORT] TTS job {job_id} generated but will not be sent to playback because person left.")
                tts_queue.task_done()
                continue

            job = AudioJob(
                job_id=int(job_id),
                sentence_text=sentence,
                wav_path=wav_out,
                created_ts=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

            motion_build_queue.put(job)
            playback_queue.put(job)

        except Exception as e:
            if delivery_token is not None:
                delivery_token["tts_error"] = type(e).__name__
            print(f"\n❌ TTS error for job {job_id}: {type(e).__name__}: {e}\n", flush=True)

        tts_queue.task_done()


def motion_builder_worker(
    motion_build_queue: queue.Queue,
    stop_event: threading.Event,
    motion_cfg: MotionRuntimeConfig,
    motion_results: Dict[int, Any],
    motion_errors: Dict[int, str],
    results_condition: threading.Condition,
    motion_builder_done_event: threading.Event,
    max_ready_jobs: int,
    max_retries: int,
    response_abort_event: Optional[threading.Event] = None,
) -> None:
    """
    Thread 2:
    Receives AudioJob -> builds motion dataframe -> stores result by job_id.

    The number of prepared jobs is bounded so a weak PC does not keep predicting
    far ahead while Unity playback needs CPU time. Prediction resumes as soon as
    playback consumes one prepared result.
    """
    ready_limit = max(1, int(max_ready_jobs))
    attempt_limit = max(1, int(max_retries) + 1)

    try:
        while not stop_event.is_set():
            with results_condition:
                while (
                    not stop_event.is_set()
                    and not (
                        response_abort_event is not None
                        and response_abort_event.is_set()
                    )
                    and len(motion_results) + len(motion_errors) >= ready_limit
                ):
                    results_condition.wait(timeout=0.05)

            if stop_event.is_set():
                break

            try:
                item = motion_build_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is SENTINEL:
                motion_build_queue.task_done()
                break

            job: AudioJob = item

            if response_abort_event is not None and response_abort_event.is_set():
                print(f"[ABORT] Skip motion job {job.job_id} because person left.")
                motion_build_queue.task_done()
                continue

            df_send = None
            err_msg = ""

            try:
                for attempt in range(1, attempt_limit + 1):
                    try:
                        print(
                            f"[MOTION] Building motion for job {job.job_id} "
                            f"(attempt {attempt}/{attempt_limit}) ..."
                        )
                        df_send = build_send_dataframe_from_wav(
                            wav_path=job.wav_path,
                            cfg=motion_cfg,
                            save_dir=motion_cfg.save_dir if motion_cfg.save_sentence_motion_csv else None,
                        )
                        err_msg = ""
                        break
                    except Exception as e:
                        err_msg = f"{type(e).__name__}: {e}"
                        if attempt < attempt_limit:
                            print(
                                f"[MOTION] Retry job {job.job_id} after failure: {err_msg}"
                            )

                with results_condition:
                    if df_send is not None:
                        motion_results[job.job_id] = df_send
                    else:
                        motion_errors[job.job_id] = err_msg or "Unknown motion build error"
                    results_condition.notify_all()

                if df_send is not None:
                    print(f"[MOTION] Ready job {job.job_id}")
                else:
                    print(f"[MOTION] Failed job {job.job_id}: {err_msg}")
            finally:
                motion_build_queue.task_done()
    finally:
        motion_builder_done_event.set()
        with results_condition:
            results_condition.notify_all()


def _drain_queue_nowait(q: queue.Queue, name: str = "queue") -> None:
    """Mark all currently queued items as done without processing them."""
    drained = 0
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        try:
            q.task_done()
        except Exception:
            pass
        drained += 1
        if item is SENTINEL:
            break
    if drained > 0:
        print(f"[ABORT] Drained {drained} pending item(s) from {name}.")


def playback_unity_worker(
    playback_queue: queue.Queue,
    stop_event: threading.Event,
    motion_cfg: MotionRuntimeConfig,
    runtime_cfg: VoiceMotionRuntimeConfig,
    tcp: UnityTcpServer,
    motion_results: Dict[int, Any],
    motion_errors: Dict[int, str],
    results_condition: threading.Condition,
    unity_person_dispatcher: UnityPersonStateDispatcher,
    playback_start_event: Optional[threading.Event] = None,
    response_abort_event: Optional[threading.Event] = None,
    response_text_sent_event: Optional[threading.Event] = None,
    on_delivered: Optional[Callable[[AudioJob], None]] = None,
    on_started: Optional[Callable[[AudioJob], None]] = None,
    delivery_token: Optional[dict] = None,
) -> None:
    """Wait for the audio gate and motion outcome, then start audio.

    Information is published through on_started immediately after sd.play.
    A motion failure can fall back to audio-only; cancellation never starts audio.
    """
    while not stop_event.is_set():
        try:
            item = playback_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if item is SENTINEL:
            playback_queue.task_done()
            break

        if response_abort_event is not None and response_abort_event.is_set():
            # Abort was requested before this queued sentence started.
            # Do not start another sentence after the user has left.
            job_to_skip = getattr(item, "job_id", "unknown")
            print(f"[ABORT] Skip playback job {job_to_skip} because person left before this sentence started.")
            playback_queue.task_done()
            _drain_queue_nowait(playback_queue, name="playback_queue")
            break

        if playback_start_event is not None:
            while (not stop_event.is_set()) and (not playback_start_event.is_set()):
                time.sleep(0.01)

            if stop_event.is_set():
                playback_queue.task_done()
                break

        job: AudioJob = item
        df_send = None
        err_msg = None
        hold_logged = False

        while not stop_event.is_set():
            if response_abort_event is not None and response_abort_event.is_set():
                # Abort requested while this queued sentence was waiting for motion.
                # Since playback has not started yet, skip it.
                print(f"[ABORT] Skip playback job {job.job_id} while waiting for motion because person left.")
                playback_queue.task_done()
                _drain_queue_nowait(playback_queue, name="playback_queue")
                return

            with results_condition:
                if job.job_id in motion_results:
                    df_send = motion_results.pop(job.job_id)
                    results_condition.notify_all()
                    break
                if job.job_id in motion_errors:
                    err_msg = motion_errors.pop(job.job_id)
                    results_condition.notify_all()
                    break

                if not hold_logged:
                    print(f"[BUFFER] HOLD playback job {job.job_id}: waiting for motion ...")
                    hold_logged = True
                results_condition.wait(
                    timeout=max(0.01, float(runtime_cfg.motion_wait_sleep_sec))
                )

        if stop_event.is_set() or (response_abort_event is not None and response_abort_event.is_set()):
            playback_queue.task_done()
            break
        play_response_audio(
            job, df_send, err_msg, runtime_cfg.play_audio_even_if_motion_failed,
            play_motion=lambda notify: send_prebuilt_motion_in_sync(
                df_send=df_send, wav_path=job.wav_path, tcp=tcp, cfg=motion_cfg,
                on_audio_started=notify),
            play_audio_only=lambda notify: play_wav_only(job.wav_path, on_audio_started=notify),
            on_started=on_started, on_delivered=on_delivered, token=delivery_token,
        )

        playback_queue.task_done()

        if response_abort_event is not None and response_abort_event.is_set():
            # Current sentence has finished. Stop before starting any further sentence.
            print(f"[ABORT] Finished current playback job {job.job_id}. Stop remaining response playback.")
            _drain_queue_nowait(playback_queue, name="playback_queue")
            break


def person_detection_worker(
    stop_event: threading.Event,
    runtime_cfg: VoiceMotionRuntimeConfig,
    tcp: UnityTcpServer,
    session_manager: RuntimeSessionManager,
    unity_person_dispatcher: UnityPersonStateDispatcher,
    active_turn_abort_controller: Optional[ActiveTurnAbortController] = None,
) -> None:
    """
    Thread 4:
    Continuous face + pose based person presence detection.
    Sends person_detection result to Unity using the same TCP connection.
    Console logs are minimized to avoid breaking input().

    Session rule:
    - When person_present changes to True: create a new session if none exists.
    - When person_present changes to False: close current session immediately.
    """
    if not runtime_cfg.enable_person_detection:
        return

    cap = cv2.VideoCapture(runtime_cfg.person_camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, runtime_cfg.person_frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, runtime_cfg.person_frame_height)

    if not cap.isOpened():
        print("[PERSON] Cannot open webcam.")
        return

    actual_capture_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_capture_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(
        f"[PERSON] Camera capture requested="
        f"{runtime_cfg.person_frame_width}x{runtime_cfg.person_frame_height} | "
        f"actual={actual_capture_w}x{actual_capture_h}"
    )

    mp_face = mp.solutions.face_detection
    mp_pose = mp.solutions.pose

    face_detector = mp_face.FaceDetection(
        model_selection=0,
        min_detection_confidence=runtime_cfg.person_face_min_det_conf,
    )

    pose_detector = mp_pose.Pose(
        static_image_mode=True,  # V13.2: explicitly kept as requested
        model_complexity=0,
        enable_segmentation=False,
        min_detection_confidence=runtime_cfg.person_pose_min_det_conf,
        min_tracking_confidence=runtime_cfg.person_pose_min_track_conf,
    )

    state = PersonDetectionState()
    last_detect_time = 0.0
    last_logged_person_present: Optional[bool] = None

    if runtime_cfg.person_detection_verbose:
        print("[PERSON] Detection thread started.")
        if runtime_cfg.visualize_person_detection:
            print("[PERSON] Visualization is ON. Press 'q' on the OpenCV window to stop detection thread.")

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                print("[PERSON] Failed to read frame.")
                time.sleep(0.1)
                continue

            # V13.2: convert the requested 1920x1080 camera frame to a
            # 1080x1920 portrait frame before detection and visualization.
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            frame = cv2.flip(frame, 1)
            frame_h, frame_w = frame.shape[:2]
            roi = calc_roi(frame_w, frame_h, runtime_cfg)
            x1_roi, y1_roi, x2_roi, y2_roi = roi

            now = time.time()
            face_info: Dict[str, Any] = {
                "valid": False,
                "bbox": None,
                "center": None,
                "reason": "No face",
            }
            pose_info: Dict[str, Any] = {
                "valid": False,
                "landmarks": None,
                "shoulder_center": None,
                "shoulder_width": None,
                "reason": "No pose",
            }

            if now - last_detect_time >= runtime_cfg.person_detect_interval_sec:
                last_detect_time = now

                face_valid, face_info = detect_face(frame, roi, face_detector, runtime_cfg)
                pose_valid, pose_info = detect_pose(frame, roi, pose_detector, runtime_cfg, mp_pose)

                state.last_face_valid = face_valid
                state.last_pose_valid = pose_valid

                # V13.2 state-dependent presence rule:
                # - Inactive: require BOTH valid Face and valid Pose to activate.
                # - Active: either valid Face OR valid Pose retains the session.
                # - Only when BOTH are invalid do consecutive misses accumulate.
                if not state.person_present:
                    activation_hit = face_valid and pose_valid
                    state.consecutive_misses = 0

                    if activation_hit:
                        state.consecutive_hits += 1
                    else:
                        state.consecutive_hits = 0

                    if (
                        state.consecutive_hits
                        >= runtime_cfg.person_required_consecutive_hits
                    ):
                        state.person_present = True
                else:
                    retention_hit = face_valid or pose_valid

                    if retention_hit:
                        state.consecutive_misses = 0
                    else:
                        state.consecutive_misses += 1

                    if (
                        state.consecutive_misses
                        >= runtime_cfg.person_required_consecutive_misses
                    ):
                        state.person_present = False
                        state.consecutive_hits = 0

                if face_valid and pose_valid:
                    state.last_reason = (
                        "VALID by FACE + POSE"
                        if state.person_present
                        else (
                            "WAIT_ACTIVATION | FACE + POSE valid | "
                            f"hits={state.consecutive_hits}/"
                            f"{runtime_cfg.person_required_consecutive_hits}"
                        )
                    )
                    state.last_face_bbox = face_info.get("bbox")
                    state.last_center = face_info.get("center")
                elif face_valid:
                    state.last_reason = (
                        "VALID by FACE | session retained"
                        if state.person_present
                        else "WAIT_ACTIVATION | FACE valid, POSE invalid"
                    )
                    state.last_face_bbox = face_info.get("bbox")
                    state.last_center = face_info.get("center")
                elif pose_valid:
                    state.last_reason = (
                        "VALID by POSE | session retained"
                        if state.person_present
                        else "WAIT_ACTIVATION | FACE invalid, POSE valid"
                    )
                    state.last_face_bbox = None
                    state.last_center = pose_info.get("shoulder_center")
                else:
                    state.last_reason = (
                        f"INVALID | Face: {face_info['reason']} | Pose: {pose_info['reason']}"
                    )
                    state.last_face_bbox = None
                    state.last_center = None

                if runtime_cfg.send_person_detection_to_unity:
                    bbox = state.last_face_bbox or (0, 0, 0, 0)
                    center = state.last_center or (0, 0)
                    unity_person_dispatcher.publish_or_defer(
                        person_present=state.person_present,
                        face_valid=state.last_face_valid,
                        pose_valid=state.last_pose_valid,
                        consecutive_hits=state.consecutive_hits,
                        consecutive_misses=state.consecutive_misses,
                        reason=state.last_reason,
                        bbox=bbox,
                        center=center,
                    )

                if last_logged_person_present is None or last_logged_person_present != state.person_present:
                    print(
                        f"[PERSON] State changed -> present={state.person_present}, "
                        f"reason={state.last_reason}"
                    )

                    # Save the exact portrait frame at both session boundaries.
                    # Close image must be saved before the session manager clears
                    # its active-session reference.
                    if not state.person_present:
                        save_person_session_event_image(
                            frame_bgr=frame,
                            session=session_manager.get_active_session(),
                            event_name="close",
                            state=state,
                            roi=roi,
                            face_info=face_info,
                            pose_info=pose_info,
                        )

                    if (not state.person_present) and active_turn_abort_controller is not None:
                        active_turn_abort_controller.request_abort(
                            reason=f"person_present_false | {state.last_reason}"
                        )

                    session_manager.handle_person_state_change(
                        person_present=state.person_present,
                        reason=state.last_reason,
                    )

                    if state.person_present:
                        save_person_session_event_image(
                            frame_bgr=frame,
                            session=session_manager.get_active_session(),
                            event_name="start",
                            state=state,
                            roi=roi,
                            face_info=face_info,
                            pose_info=pose_info,
                        )

                    last_logged_person_present = state.person_present
                elif runtime_cfg.person_detection_verbose:
                    print(
                        f"[PERSON] Detect tick -> present={state.person_present}, "
                        f"face={state.last_face_valid}, pose={state.last_pose_valid}, "
                        f"hits={state.consecutive_hits}, misses={state.consecutive_misses}, "
                        f"reason={state.last_reason}"
                    )

            if runtime_cfg.visualize_person_detection:
                cv2.rectangle(frame, (x1_roi, y1_roi), (x2_roi, y2_roi), (0, 255, 255), 2)

                if state.last_face_bbox is not None:
                    x, y, w, h = state.last_face_bbox
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

                if state.last_center is not None:
                    cv2.circle(frame, state.last_center, 5, (0, 255, 255), -1)

                status_text = "PERSON PRESENT" if state.person_present else "NO PERSON"
                status_color = (0, 255, 0) if state.person_present else (0, 0, 255)
                cv2.putText(
                    frame,
                    status_text,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    status_color,
                    2,
                )

                cv2.putText(
                    frame,
                    f"Face={state.last_face_valid} | Pose={state.last_pose_valid}",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                cv2.putText(
                    frame,
                    f"Hits={state.consecutive_hits} | Misses={state.consecutive_misses}",
                    (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                cv2.putText(
                    frame,
                    f"Interval={runtime_cfg.person_detect_interval_sec:.1f}s",
                    (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                time_left = max(0.0, runtime_cfg.person_detect_interval_sec - (now - last_detect_time))
                cv2.putText(
                    frame,
                    f"Next detect in {time_left:.1f}s",
                    (20, 170),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                reason_show = state.last_reason[:100]
                cv2.putText(
                    frame,
                    reason_show,
                    (20, frame_h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (200, 200, 200),
                    1,
                )

                cv2.imshow("Face + Pose Presence Detection", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[PERSON] Visualization window closed by user.")
                    break

            time.sleep(runtime_cfg.person_loop_sleep_sec)

    except Exception as e:
        print(f"[PERSON] Detection thread error: {type(e).__name__}: {e}")

    finally:
        try:
            cap.release()
        except Exception:
            pass

        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        try:
            face_detector.close()
        except Exception:
            pass

        try:
            pose_detector.close()
        except Exception:
            pass

        if runtime_cfg.person_detection_verbose:
            print("[PERSON] Detection thread stopped.")


# ============================================================
# MAIN LOOP
# ============================================================
def wait_for_greeting_readiness_delay(
    session_manager: RuntimeSessionManager,
    session: SessionContext,
    delay_sec: float,
    stop_event: threading.Event,
) -> bool:
    """
    Wait until the configured time has elapsed since person-session creation.

    Returns False if the runtime stops or this session is no longer active, so an
    old greeting cannot play after the detected person has already left.
    """
    delay_sec = max(0.0, float(delay_sec))
    deadline = session.started_monotonic + delay_sec
    remaining = max(0.0, deadline - time.monotonic())

    if remaining > 0.0:
        print(
            f"[GREETING] Unity readiness delay: wait {remaining:.2f}s "
            f"before greeting session {session.session_id}"
        )

    while True:
        if stop_event.is_set():
            return False
        if session_manager.get_active_session() is not session:
            return False

        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return True
        time.sleep(min(0.05, remaining))


def start_record_session_guard(
    session_manager: RuntimeSessionManager,
    start_generation: int,
    record_stop_event: threading.Event,
    runtime_stop_event: threading.Event,
    poll_sec: float = 0.05,
) -> threading.Thread:
    """
    Stop microphone recording if person detection creates/closes a session.

    Reason:
    - Greeting audio is played by the main loop before recording.
    - However, record_wav_by_volume_trigger() can block while waiting for speech.
    - If person detection closes the old session and creates a new one during that
      blocking wait, the main loop must be released so it can return to the top
      and play greeting for the new session before accepting user speech.
    """

    def _guard() -> None:
        while not record_stop_event.is_set():
            if runtime_stop_event.is_set():
                record_stop_event.set()
                break
            if session_manager.has_session_changed_since(start_generation):
                record_stop_event.set()
                break
            time.sleep(poll_sec)

    t = threading.Thread(target=_guard, daemon=True)
    t.start()
    return t


def cleanup_turn_threads(
    tts_queue: queue.Queue,
    motion_build_queue: queue.Queue,
    playback_queue: queue.Queue,
    tts_thread: threading.Thread,
    motion_thread: threading.Thread,
    playback_thread: threading.Thread,
    stop_event: threading.Event,
) -> None:
    """
    Stop and join the three per-turn worker threads safely.
    """
    stop_event.set()

    for q in (tts_queue, motion_build_queue, playback_queue):
        try:
            q.put_nowait(SENTINEL)
        except Exception:
            pass

    try:
        tts_thread.join(timeout=2.0)
    except Exception:
        pass

    try:
        motion_thread.join(timeout=2.0)
    except Exception:
        pass

    try:
        playback_thread.join(timeout=2.0)
    except Exception:
        pass


def is_initial_motion_buffer_pending(
    motion_results: Dict[int, Any],
    motion_errors: Dict[int, str],
    results_condition: threading.Condition,
    motion_builder_done_event: threading.Event,
    response_abort_event: threading.Event,
    target_jobs: int,
) -> bool:
    """Return True only when the existing initial-buffer gate would wait."""
    target = max(1, int(target_jobs))
    with results_condition:
        prepared_count = len(motion_results) + len(motion_errors)
        return not (
            prepared_count >= target
            or motion_builder_done_event.is_set()
            or response_abort_event.is_set()
        )


def clear_searching_text_if_unreplaced(
    tcp: UnityTcpServer,
    searching_text_sent: bool,
    response_text_sent_event: threading.Event,
) -> None:
    """Clear only an unresolved searching status, never a real response text."""
    if not searching_text_sent or response_text_sent_event.is_set():
        return

    try:
        tcp.send_clear_speech_text()
        print("[TEXT] Cleared unresolved searching status")
    except Exception as e:
        print(f"[TEXT] Failed to clear searching status: {type(e).__name__}: {e}")


def wait_for_initial_motion_buffer(
    motion_results: Dict[int, Any],
    motion_errors: Dict[int, str],
    results_condition: threading.Condition,
    motion_builder_done_event: threading.Event,
    response_abort_event: threading.Event,
    target_jobs: int,
    wait_timeout_sec: float,
) -> None:
    """
    Hold the response playback gate until a small initial motion buffer is ready.

    This is readiness-based, not a fixed sleep. If the response contains fewer
    sentences than the target, the gate opens as soon as the builder is done.
    """
    target = max(1, int(target_jobs))
    hold_logged = False

    with results_condition:
        while True:
            ready_count = len(motion_results)
            failed_count = len(motion_errors)
            prepared_count = ready_count + failed_count

            if (
                prepared_count >= target
                or motion_builder_done_event.is_set()
                or response_abort_event.is_set()
            ):
                print(
                    f"[BUFFER] Initial buffer released: ready={ready_count}, "
                    f"failed={failed_count}, target={target}, "
                    f"builder_done={motion_builder_done_event.is_set()}"
                )
                return

            if not hold_logged:
                print(
                    f"[BUFFER] HOLD generated response until {target} motion job(s) "
                    "are prepared ..."
                )
                hold_logged = True

            results_condition.wait(timeout=max(0.01, float(wait_timeout_sec)))


def response_generation_worker(
    turn: TurnContext,
    session: SessionContext,
    memory: ConversationMemory,
    kb_store: LocalKBStore,
    tts_queue: queue.Queue,
    stop_event: threading.Event,
    state: ResponseThreadState,
    stt_done_event: Optional[threading.Event] = None,
    response_abort_event: Optional[threading.Event] = None,
    active_turn_abort_controller: Optional[ActiveTurnAbortController] = None,
    panel_sender=None,
) -> None:
    """
    Per-turn response preparation worker.
    This runs STT/LLM/ElevenLabs queueing while the main thread can play waiting audio.
    Actual response playback is still handled by playback_unity_worker and can be gated.
    """
    try:
        # 1) STT
        transcript = speech_to_text(turn.wav_in_path)
        state.transcript = transcript
        turn.user_transcript_path.write_text(transcript, encoding="utf-8")

        if not has_real_transcript_text(transcript):
            state.no_speech = True
            state.status = "no_speech_detected"
            state.error = "No real speech text detected"
            if stt_done_event is not None:
                stt_done_event.set()
            print("⚠️ No real speech text detected. Skip waiting audio and response generation.\n")
            tts_queue.put(SENTINEL)
            return

        if stt_done_event is not None:
            stt_done_event.set()

        print(f"\n📝 Transcript:\n{transcript}\n")

        # Save user turn to memory
        memory.add_turn("user", transcript)
        memory.save()

        print("💬 Assistant (streaming):\n", end="", flush=True)

        # 2) LLM streaming -> sentence queue -> TTS worker
        full_answer = llm_stream_to_tts_queue(
            transcript,
            tts_queue,
            stop_event,
            memory=memory,
            kb_store=kb_store,
            response_abort_event=response_abort_event,
            delivery_token=turn.v17_delivery,
            send_panel=panel_sender, turn_id=turn.turn_id,
        )

        turn.assistant_response_path.with_suffix(".v17.json").write_text(
            json.dumps(turn.v17_delivery.get("response", {}), ensure_ascii=False, indent=2), encoding="utf-8")
        turn.assistant_response_path.with_suffix(".delivery.json").write_text(
            json.dumps({key: value for key, value in dict(turn.v17_delivery).items()
                        if key != "response"}, ensure_ascii=False, indent=2), encoding="utf-8")
        state.full_answer = full_answer
        turn.assistant_response_path.write_text(full_answer, encoding="utf-8")

        if response_abort_event is not None and response_abort_event.is_set():
            state.aborted_by_person_left = True
            state.abort_reason = (
                active_turn_abort_controller.get_abort_reason()
                if active_turn_abort_controller is not None
                else "person_left"
            )
            state.status = "aborted_person_left"
            print(f"[ABORT] Response generation stopped early. reason={state.abort_reason}")
        else:
            # Save assistant turn only when the response completed normally.
            memory.add_turn("assistant", full_answer)
            memory.save()

            # Update summary/facts periodically
            # V17 uses terminal-gated tree evidence; no parallel legacy summary/facts API calls.
            state.status = "completed"

        # Signal no more sentences
        tts_queue.put(SENTINEL)

    except Exception as e:
        state.status = "error"
        state.error = f"{type(e).__name__}: {e}"
        if stt_done_event is not None:
            stt_done_event.set()
        print(f"\n❌ Response generation error: {state.error}\n")
        try:
            tts_queue.put_nowait(SENTINEL)
        except Exception:
            pass


def main() -> None:
    _launch_virtual_officer_shortcut()

    cfg = VoiceMotionRuntimeConfig()

    validate_motion_config(cfg.motion_cfg)
    cfg.sessions_root_dir.mkdir(parents=True, exist_ok=True)

    preset_motion_cache = load_preset_motion_cache(
        audio_dirs=(
            cfg.greeting_audios_dir,
            cfg.waiting_audios_dir,
        ),
        extensions=cfg.preset_audio_extensions,
    )

    print("\n=== Voice Motion Runtime V17.2: local model-only split-output agent ===")
    print("Auto-record mode: speak to start recording.")
    print("Recording stops when volume returns to neutral for the configured silence duration.")
    print("Press Ctrl+C to quit.\n")

    session_manager = RuntimeSessionManager(sessions_root_dir=cfg.sessions_root_dir)
    # V17: load the tree and operational overlay; legacy vector classes are inactive.
    kb_store = KnowledgeBase(KB_DIR)

    temp_record_dir = OUT_DIR / "temp_auto_record"
    temp_record_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Sessions root] {cfg.sessions_root_dir}")
    print(f"[KB dir] {KB_DIR}")
    print(f"[Greeting audios] {cfg.greeting_audios_dir}")
    print(f"[Waiting audios] {cfg.waiting_audios_dir}")
    print(f"[Unity] host={cfg.motion_cfg.host} port={cfg.motion_cfg.port}")
    print(
        f"[Auto Record] enabled={cfg.enable_auto_recording}, "
        f"neutral_calibration={cfg.volume_trigger_cfg.mic_neutral_calibration_sec:.2f}s, "
        f"frame={cfg.volume_trigger_cfg.mic_frame_ms}ms, "
        f"pre_roll={cfg.volume_trigger_cfg.pre_roll_sec:.2f}s, "
        f"silence_stop={cfg.volume_trigger_cfg.silence_stop_sec:.2f}s, "
        f"max_record={cfg.volume_trigger_cfg.max_record_sec:.2f}s"
    )
    print(
        f"[Person Detection] enabled={cfg.enable_person_detection}, "
        f"visualize={cfg.visualize_person_detection}, "
        f"verbose={cfg.person_detection_verbose}\n"
    )
    print(
        f"[V12.1 Lite] initial_motion_buffer={cfg.initial_motion_buffer_jobs}, "
        f"max_ready_motion={cfg.max_ready_motion_jobs}, "
        f"motion_retries={cfg.motion_build_max_retries}, "
        f"greeting_delay={cfg.person_greeting_delay_sec:.2f}s, "
        f"audio_without_motion={cfg.play_audio_even_if_motion_failed}, "
        f"searching_ui={cfg.send_searching_text_to_unity}\n"
    )

    tcp = UnityTcpServer(host=cfg.motion_cfg.host, port=cfg.motion_cfg.port)
    unity_person_dispatcher = UnityPersonStateDispatcher(
        tcp=tcp,
        enabled=cfg.send_person_detection_to_unity,
    )
    unity_mic_dispatcher = UnityMicrophoneStateDispatcher(
        tcp=tcp,
        enabled=True,
    )
    active_turn_abort_controller = ActiveTurnAbortController()
    person_stop_event = threading.Event()
    person_thread: Optional[threading.Thread] = None

    try:
        print("[Unity] Waiting for client connection ...")
        tcp.start_and_wait_for_client()
        print("[Unity] Client connected.\n")

        if cfg.enable_person_detection:
            person_thread = threading.Thread(
                target=person_detection_worker,
                args=(person_stop_event, cfg, tcp, session_manager, unity_person_dispatcher, active_turn_abort_controller),
                daemon=True,
            )
            person_thread.start()
        else:
            session_manager.handle_person_state_change(
                person_present=True,
                reason="person_detection_disabled",
            )

        # One-time neutral microphone calibration.
        # The measured neutral_dbfs is reused for all subsequent turns in this run.
        calibrated_neutral_dbfs: Optional[float] = None
        if cfg.enable_auto_recording:
            calibrated_neutral_dbfs = calibrate_neutral_dbfs(
                cfg.volume_trigger_cfg,
                stop_event=person_stop_event,
                verbose=cfg.verbose,
            )
            print(
                f"[AUTO-REC] One-time calibration complete | "
                f"neutral_dbfs={calibrated_neutral_dbfs:.2f}, "
                f"start_threshold={calibrated_neutral_dbfs + cfg.volume_trigger_cfg.start_margin_db:.2f}, "
                f"stop_threshold={calibrated_neutral_dbfs + cfg.volume_trigger_cfg.stop_margin_db:.2f}"
            )

        last_wait_log_ts = 0.0
        temp_record_index = 0
        while True:
            active_session = session_manager.get_active_session()
            if active_session is None:
                unity_mic_dispatcher.set_mic_state(
                    False,
                    reason="no_active_session",
                    session_id="",
                    turn_id="",
                )
                now = time.time()
                if now - last_wait_log_ts >= 2.0:
                    print("[SESSION] No active session. Waiting for person_present=True ...")
                    last_wait_log_ts = now
                time.sleep(0.1)
                continue

            # Play greeting preset once for each newly created session.
            # The greeting state is owned by RuntimeSessionManager, not by a local
            # object-identity variable, so session recreation from person detection
            # is handled reliably across threads.
            greeting_session = session_manager.claim_greeting_for_active_session()
            if greeting_session is not None:
                unity_mic_dispatcher.set_mic_state(
                    False,
                    reason="waiting_before_greeting_audio",
                    session_id=greeting_session.session_id,
                    turn_id="",
                )
                greeting_ready = wait_for_greeting_readiness_delay(
                    session_manager=session_manager,
                    session=greeting_session,
                    delay_sec=cfg.person_greeting_delay_sec,
                    stop_event=person_stop_event,
                )
                if not greeting_ready:
                    print(
                        f"[GREETING] Skip stale greeting for session "
                        f"{greeting_session.session_id}"
                    )
                    continue

                greeting_wav = choose_random_audio(
                    cfg.greeting_audios_dir,
                    extensions=cfg.preset_audio_extensions,
                )

                if greeting_wav is not None:
                    greeting_text = read_preset_text_for_unity(greeting_wav)
                    greeting_save_dir = greeting_session.logs_dir / "preset_greeting_motion"
                    unity_mic_dispatcher.set_mic_state(
                        False,
                        reason="playing_greeting_audio",
                        session_id=greeting_session.session_id,
                        turn_id="",
                    )
                    run_existing_wav_with_motion(
                        wav_path=greeting_wav,
                        preset_name="greeting",
                        job_id=cfg.preset_job_id_greeting,
                        motion_cfg=cfg.motion_cfg,
                        runtime_cfg=cfg,
                        tcp=tcp,
                        unity_person_dispatcher=unity_person_dispatcher,
                        preset_motion_cache=preset_motion_cache,
                        save_dir=greeting_save_dir,
                        display_text=greeting_text,
                    )
                else:
                    print(f"[PRESET] No greeting WAV found in: {cfg.greeting_audios_dir}")

                # Always restart the loop after greeting playback.
                # This handles the edge case where person detection closes this
                # session and creates another one while greeting audio is still
                # playing. The next loop will claim/play greeting for the newest
                # active session before microphone recording starts.
                continue

            unity_mic_dispatcher.set_mic_state(
                True,
                reason="ready_to_record",
                session_id=active_session.session_id,
                turn_id="",
            )
            print(f"\n[session={active_session.session_id}] Waiting for user speech ...")

            # Record into a temporary WAV first.
            # A formal turn folder is created only after a valid recording exists.
            temp_record_index += 1
            temp_wav_path = temp_record_dir / f"auto_record_{_session_id_now()}_{temp_record_index:04d}.wav"

            # Capture the session identity before recording starts.
            # If person detection closes/recreates the session while the recorder
            # is blocking, the guard stops recording and this loop restarts so
            # greeting can run for the new session before accepting speech.
            record_session_id = active_session.session_id
            record_session_generation = session_manager.get_session_generation()
            record_stop_event = threading.Event()
            record_guard_thread = start_record_session_guard(
                session_manager=session_manager,
                start_generation=record_session_generation,
                record_stop_event=record_stop_event,
                runtime_stop_event=person_stop_event,
            )

            try:
                if cfg.enable_auto_recording:
                    record_result = record_wav_by_volume_trigger(
                        path=temp_wav_path,
                        cfg=cfg.volume_trigger_cfg,
                        neutral_dbfs=calibrated_neutral_dbfs,
                        stop_event=record_stop_event,
                        verbose=cfg.verbose,
                    )
                else:
                    record_wav(temp_wav_path, cfg.record_seconds)
                    record_result = None
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[AUTO-REC] Recording error: {type(e).__name__}: {e}")
                time.sleep(0.2)
                continue
            finally:
                record_stop_event.set()
                try:
                    record_guard_thread.join(timeout=0.2)
                except Exception:
                    pass

            current_after_record = session_manager.get_active_session()
            if (
                session_manager.has_session_changed_since(record_session_generation)
                or current_after_record is None
                or current_after_record.session_id != record_session_id
            ):
                unity_mic_dispatcher.set_mic_state(
                    False,
                    reason="session_changed_during_recording",
                    session_id=record_session_id,
                    turn_id="",
                )
                print("[SESSION] Session changed during recording. Discard recording and restart loop for greeting check.")
                try:
                    temp_wav_path.unlink(missing_ok=True)
                except Exception:
                    pass
                time.sleep(0.1)
                continue

            if cfg.enable_auto_recording and record_result is not None and not record_result.saved:
                print(f"[AUTO-REC] No valid recording. reason={record_result.reason}")
                time.sleep(0.2)
                continue

            unity_mic_dispatcher.set_mic_state(
                False,
                reason="processing_after_record",
                session_id=record_session_id,
                turn_id="",
            )

            # If the user left during recording, discard this temporary recording.
            session_and_turn = session_manager.create_turn_for_active_session()
            if session_and_turn is None:
                unity_mic_dispatcher.set_mic_state(
                    False,
                    reason="session_ended_before_processing",
                    session_id=record_session_id,
                    turn_id="",
                )
                print("[SESSION] Session ended before processing. Discard this recording.")
                try:
                    temp_wav_path.unlink(missing_ok=True)
                except Exception:
                    pass
                time.sleep(0.1)
                continue

            session, turn = session_and_turn
            memory = session.memory
            save_memory_snapshot(memory, turn.memory_before_path)

            try:
                # Move temporary input WAV into this turn folder.
                turn.wav_in_path.parent.mkdir(parents=True, exist_ok=True)
                if temp_wav_path.exists():
                    try:
                        temp_wav_path.replace(turn.wav_in_path)
                    except Exception:
                        # Fallback for cross-device moves.
                        shutil.copy2(str(temp_wav_path), str(turn.wav_in_path))
                        temp_wav_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"[AUDIO] Failed to move recorded WAV into turn folder: {type(e).__name__}: {e}")
                session_manager.finalize_turn(
                    session=session,
                    turn=turn,
                    status="error",
                    user_text="",
                    assistant_text="",
                    error=f"Failed to move recorded WAV: {type(e).__name__}: {e}",
                )
                continue

            if cfg.enable_auto_recording and record_result is not None:
                append_jsonl(
                    turn.logs_dir / "auto_record.jsonl",
                    {
                        "ts": _ts_now(),
                        "saved": record_result.saved,
                        "duration_sec": record_result.duration_sec,
                        "neutral_dbfs": record_result.neutral_dbfs,
                        "start_threshold_dbfs": record_result.start_threshold_dbfs,
                        "stop_threshold_dbfs": record_result.stop_threshold_dbfs,
                        "reason": record_result.reason,
                        "temp_wav_path": str(record_result.wav_path),
                        "final_wav_path": str(turn.wav_in_path),
                    },
                )

            stop_event = threading.Event()
            response_abort_event = threading.Event()
            active_turn_abort_controller.start_turn(
                session_id=session.session_id,
                turn_id=turn.turn_id,
                response_abort_event=response_abort_event,
            )

            # From here the assistant response pipeline is active.
            # While response audio/motion is being played, defer Unity-facing person updates.
            unity_person_dispatcher.set_playback_busy(True)

            tts_queue: queue.Queue = queue.Queue(maxsize=cfg.max_queue_size)
            motion_build_queue: queue.Queue = queue.Queue(maxsize=cfg.max_queue_size)
            playback_queue: queue.Queue = queue.Queue(maxsize=cfg.max_queue_size)

            motion_results: Dict[int, Any] = {}
            motion_errors: Dict[int, str] = {}
            results_condition = threading.Condition()
            motion_builder_done_event = threading.Event()

            # Closed gate: generated response audio/motion may be prepared in background,
            # but it cannot play until waiting preset audio has finished.
            response_playback_start_event = threading.Event()
            response_text_sent_event = threading.Event()

            turn_motion_cfg = copy.deepcopy(cfg.motion_cfg)
            turn_motion_cfg.save_dir = str(turn.motions_dir)

            turn.v17_delivery = {}
            tts_thread = threading.Thread(
                target=tts_worker_v2,
                args=(
                    tts_queue,
                    motion_build_queue,
                    playback_queue,
                    stop_event,
                    turn.wav_prefix,
                    turn.audio_out_dir,
                    response_abort_event,
                    turn.v17_delivery,
                ),
                daemon=True,
            )
            motion_thread = threading.Thread(
                target=motion_builder_worker,
                args=(
                    motion_build_queue,
                    stop_event,
                    turn_motion_cfg,
                    motion_results,
                    motion_errors,
                    results_condition,
                    motion_builder_done_event,
                    cfg.max_ready_motion_jobs,
                    cfg.motion_build_max_retries,
                    response_abort_event,
                ),
                daemon=True,
            )
            def send_panel_to_unity(packet, response_text_sent_event=response_text_sent_event):
                tcp.send_message(packet)
                if packet.get("type") == "speech_text":
                    response_text_sent_event.set()

            playback_thread = threading.Thread(
                target=playback_unity_worker,
                args=(
                    playback_queue,
                    stop_event,
                    turn_motion_cfg,
                    cfg,
                    tcp,
                    motion_results,
                    motion_errors,
                    results_condition,
                    unity_person_dispatcher,
                    response_playback_start_event,
                    response_abort_event,
                    response_text_sent_event,
                    lambda job, mem=memory, token=turn.v17_delivery: acknowledge_playback(mem, token, job),
                    lambda job, token=turn.v17_delivery, sender=send_panel_to_unity: publish_information_on_playback(token, sender),
                    turn.v17_delivery,
                ),
                daemon=True,
            )

            playback_thread.start()
            motion_thread.start()
            tts_thread.start()

            transcript = ""
            full_answer = ""
            searching_text_sent = False

            try:
                response_state = ResponseThreadState()
                stt_done_event = threading.Event()

                response_thread = threading.Thread(
                    target=response_generation_worker,
                    args=(
                        turn,
                        session,
                        memory,
                        kb_store,
                        tts_queue,
                        stop_event,
                        response_state,
                        stt_done_event,
                        response_abort_event,
                        active_turn_abort_controller,
                        send_panel_to_unity,
                    ),
                    daemon=True,
                )
                response_thread.start()

                # Wait until OpenAI STT has returned.
                # Waiting preset audio is played only when the recorded file contains
                # a real transcript. This avoids playing waiting audio for noise-only
                # recordings. LLM/TTS/motion preparation may continue in background
                # while waiting preset audio is playing.
                stt_done_event.wait()

                if response_state.no_speech:
                    print("[PRESET] Skip waiting audio because STT returned no real text.")
                elif response_state.status == "error" and not has_real_transcript_text(response_state.transcript):
                    print("[PRESET] Skip waiting audio because STT/response generation failed before valid transcript.")
                else:
                    waiting_wav = choose_random_audio(
                        cfg.waiting_audios_dir,
                        extensions=cfg.preset_audio_extensions,
                    )

                    if waiting_wav is not None:
                        waiting_text = read_preset_text_for_unity(waiting_wav)
                        waiting_save_dir = turn.logs_dir / "preset_waiting_motion"
                        unity_mic_dispatcher.set_mic_state(
                            False,
                            reason="playing_waiting_audio",
                            session_id=session.session_id,
                            turn_id=turn.turn_id,
                        )
                        run_existing_wav_with_motion(
                            wav_path=waiting_wav,
                            preset_name="waiting",
                            job_id=cfg.preset_job_id_waiting,
                            motion_cfg=turn_motion_cfg,
                            runtime_cfg=cfg,
                            tcp=tcp,
                            unity_person_dispatcher=unity_person_dispatcher,
                            preset_motion_cache=preset_motion_cache,
                            save_dir=waiting_save_dir,
                            display_text=waiting_text,
                        )
                    else:
                        print(f"[PRESET] No waiting WAV found in: {cfg.waiting_audios_dir}")

                initial_buffer_target = min(
                    cfg.initial_motion_buffer_jobs,
                    cfg.max_ready_motion_jobs,
                )

                # Waiting preset is finished or skipped. If valid microphone text
                # exists but the unchanged initial buffer still needs time, update
                # Unity once. The first real sentence text will overwrite it.
                if (
                    cfg.send_searching_text_to_unity
                    and cfg.send_speech_text_to_unity
                    and has_real_transcript_text(response_state.transcript)
                    and is_initial_motion_buffer_pending(
                        motion_results=motion_results,
                        motion_errors=motion_errors,
                        results_condition=results_condition,
                        motion_builder_done_event=motion_builder_done_event,
                        response_abort_event=response_abort_event,
                        target_jobs=initial_buffer_target,
                    )
                ):
                    try:
                        tcp.send_speech_text(
                            text=cfg.searching_text,
                            job_id=cfg.searching_text_job_id,
                        )
                        searching_text_sent = True
                        print(f"[TEXT] Sent searching status: {cfg.searching_text}")
                    except Exception as e:
                        print(
                            f"[TEXT] Failed to send searching status: "
                            f"{type(e).__name__}: {e}"
                        )

                # Build only a small initial readiness buffer; do not wait for the
                # whole response motion.
                wait_for_initial_motion_buffer(
                    motion_results=motion_results,
                    motion_errors=motion_errors,
                    results_condition=results_condition,
                    motion_builder_done_event=motion_builder_done_event,
                    response_abort_event=response_abort_event,
                    target_jobs=initial_buffer_target,
                    wait_timeout_sec=cfg.motion_wait_sleep_sec,
                )

                # The playback worker now consumes each prepared job. If a later
                # sentence is not ready, it holds without playing audio-only.
                unity_mic_dispatcher.set_mic_state(
                    False,
                    reason="playing_response_audio",
                    session_id=session.session_id,
                    turn_id=turn.turn_id,
                )
                response_playback_start_event.set()

                # Wait response-generation worker and all pipeline stages.
                response_thread.join()

                tts_queue.join()
                tts_thread.join(timeout=10.0)

                motion_build_queue.join()
                motion_thread.join(timeout=10.0)

                playback_queue.join()
                playback_thread.join(timeout=10.0)

                _safe_write_json(turn.assistant_response_path.with_suffix(".delivery.json"),
                    {key: value for key, value in dict(turn.v17_delivery).items() if key != "response"})
                audio_error = turn.v17_delivery.get("tts_error") or turn.v17_delivery.get("playback_error")
                if audio_error and not turn.v17_delivery.get("audio_completed"):
                    response_state.status = "error"
                    response_state.error = "Audio pipeline: " + str(audio_error)

                clear_searching_text_if_unreplaced(
                    tcp=tcp,
                    searching_text_sent=searching_text_sent,
                    response_text_sent_event=response_text_sent_event,
                )

                transcript = response_state.transcript
                full_answer = response_state.full_answer

                unity_person_dispatcher.set_playback_busy(False)
                unity_person_dispatcher.flush_pending()

                save_memory_snapshot(memory, turn.memory_after_path)

                if response_state.no_speech:
                    session_manager.finalize_turn(
                        session=session,
                        turn=turn,
                        status="no_speech_detected",
                        user_text="",
                        assistant_text="",
                        error=response_state.error or "No speech detected",
                    )
                    active_turn_abort_controller.clear_turn(turn_id=turn.turn_id)
                    continue

                if response_state.aborted_by_person_left or response_state.status == "aborted_person_left":
                    session_manager.finalize_turn(
                        session=session,
                        turn=turn,
                        status="aborted_person_left",
                        user_text=transcript,
                        assistant_text=full_answer,
                        error=response_state.abort_reason or "person_left",
                    )
                    active_turn_abort_controller.clear_turn(turn_id=turn.turn_id)
                    print("\n[ABORT] Done. User left, response stopped after current sentence. Returning to wait mode.\n")
                    continue

                if response_state.status == "error":
                    session_manager.finalize_turn(
                        session=session,
                        turn=turn,
                        status="error",
                        user_text=transcript,
                        assistant_text=full_answer,
                        error=response_state.error,
                    )
                    active_turn_abort_controller.clear_turn(turn_id=turn.turn_id)
                    continue

                if cfg.clear_speech_text_after_response:
                    try:
                        tcp.send_clear_speech_text()
                        print("[TEXT] Cleared speech text after response")
                    except Exception as e:
                        print(f"[TEXT] Failed to clear speech text: {type(e).__name__}: {e}")

                session_manager.finalize_turn(
                    session=session,
                    turn=turn,
                    status="completed",
                    user_text=transcript,
                    assistant_text=full_answer,
                    error="",
                )
                active_turn_abort_controller.clear_turn(turn_id=turn.turn_id)

                unity_mic_dispatcher.set_mic_state(
                    False,
                    reason="turn_completed_returning_to_record_loop",
                    session_id=session.session_id,
                    turn_id=turn.turn_id,
                )

                print("\n\n✅ Done. Returning to auto-record mode.\n")

            except KeyboardInterrupt:
                print("\n⚠️ Interrupted.\n")
                response_playback_start_event.set()
                cleanup_turn_threads(
                    tts_queue,
                    motion_build_queue,
                    playback_queue,
                    tts_thread,
                    motion_thread,
                    playback_thread,
                    stop_event,
                )
                clear_searching_text_if_unreplaced(
                    tcp=tcp,
                    searching_text_sent=searching_text_sent,
                    response_text_sent_event=response_text_sent_event,
                )

                unity_person_dispatcher.set_playback_busy(False)
                unity_person_dispatcher.flush_pending()

                save_memory_snapshot(memory, turn.memory_after_path)
                session_manager.finalize_turn(
                    session=session,
                    turn=turn,
                    status="interrupted",
                    user_text=transcript,
                    assistant_text=full_answer,
                    error="KeyboardInterrupt",
                )
                active_turn_abort_controller.clear_turn(turn_id=turn.turn_id)
                break

            except Exception as e:
                print(f"\n❌ Error: {type(e).__name__}: {e}\n")
                response_playback_start_event.set()
                cleanup_turn_threads(
                    tts_queue,
                    motion_build_queue,
                    playback_queue,
                    tts_thread,
                    motion_thread,
                    playback_thread,
                    stop_event,
                )
                clear_searching_text_if_unreplaced(
                    tcp=tcp,
                    searching_text_sent=searching_text_sent,
                    response_text_sent_event=response_text_sent_event,
                )

                unity_person_dispatcher.set_playback_busy(False)
                unity_person_dispatcher.flush_pending()

                save_memory_snapshot(memory, turn.memory_after_path)
                session_manager.finalize_turn(
                    session=session,
                    turn=turn,
                    status="error",
                    user_text=transcript,
                    assistant_text=full_answer,
                    error=f"{type(e).__name__}: {e}",
                )
                active_turn_abort_controller.clear_turn(turn_id=turn.turn_id)

    except KeyboardInterrupt:
        print("\n⚠️ Runtime stopped by user.\n")

    finally:
        try:
            person_stop_event.set()
        except Exception:
            pass

        try:
            if person_thread is not None and person_thread.is_alive():
                person_thread.join(timeout=2.0)
        except Exception:
            pass

        try:
            sd.stop()
        except Exception:
            pass

        try:
            unity_person_dispatcher.set_playback_busy(False)
            unity_person_dispatcher.flush_pending()
        except Exception:
            pass

        try:
            unity_mic_dispatcher.set_mic_state(
                False,
                reason="runtime_shutdown",
                session_id="",
                turn_id="",
                force=True,
            )
        except Exception:
            pass

        try:
            session_manager.shutdown(reason="runtime_shutdown")
        except Exception:
            pass

        tcp.close()

    print("Bye.")


if __name__ == "__main__":
    main()


"""
Abbreviations:
- STT: Speech-to-Text, chuyển giọng nói thành văn bản.
- LLM: Large Language Model, mô hình ngôn ngữ lớn.
- TTS: Text-to-Speech, chuyển văn bản thành giọng nói.
- WAV: Waveform Audio File Format, định dạng tệp âm thanh WAV.
- PCM: Pulse-Code Modulation, dữ liệu âm thanh số thô chưa nén.
- KB: Knowledge Base, kho tri thức.
- RAG: Retrieval-Augmented Generation, tạo sinh có tăng cường truy hồi dữ liệu.
- TCP: Transmission Control Protocol, giao thức truyền tải tin cậy.
- JSON: JavaScript Object Notation, định dạng dữ liệu kiểu đối tượng.
- ROI: Region of Interest, vùng quan tâm trong ảnh.
- RMS: Root Mean Square, giá trị hiệu dụng dùng để đo cường độ tín hiệu âm thanh.
- dBFS: Decibels relative to Full Scale, đơn vị đo âm lượng trong audio số.
- MIC: Microphone, micro thu âm đầu vào.
"""
