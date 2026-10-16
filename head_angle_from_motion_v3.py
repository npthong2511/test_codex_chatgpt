# head_angle_from_motion_v3.py
# ============================================================
# Convert motion features to roll/yaw using simple scalar mapping
#
# Requested mapping:
#   1) yaw is based only on mid_ear_to_nose_z
#      yaw = (mid_ear_to_nose_z - mean) / (2 * std) * angle_range
#
#   2) roll is based only on ear_vec_y
#      roll = (ear_vec_y - mean) / (2 * std) * angle_range
#
# The mean and std are computed from the input dataframe itself.
#
# v3 update:
#   - Add fade-in / fade-out envelope so motion starts at 0
#     and returns to 0 at the end.
#   - Envelope is applied after smoothing.
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class HeadAngleConfig:
    # --------------------------------------------------------
    # Output angle clamp
    # --------------------------------------------------------
    roll_min_deg: float = -50.0
    roll_max_deg: float = 50.0
    yaw_min_deg: float = -80.0
    yaw_max_deg: float = 80.0

    # --------------------------------------------------------
    # Angle range used in the requested formulas
    # roll = ((ear_vec_y - mean) / (2*std)) * roll_angle_range_deg
    # yaw  = ((mid_ear_to_nose_z - mean) / (2*std)) * yaw_angle_range_deg
    # --------------------------------------------------------
    roll_angle_range_deg: float = 40.0
    yaw_angle_range_deg: float = 60.0

    # --------------------------------------------------------
    # Signs / offsets for Unity alignment
    # --------------------------------------------------------
    roll_sign: float = 1.0
    yaw_sign: float = 1.0
    roll_offset_deg: float = 0.0
    yaw_offset_deg: float = 0.0

    # --------------------------------------------------------
    # Final smoothing on output angles
    # --------------------------------------------------------
    smooth_alpha: float = 0.25

    # --------------------------------------------------------
    # Fade-in / fade-out envelope
    # Applied AFTER smoothing
    # --------------------------------------------------------
    use_fade_envelope: bool = True
    fade_ratio: float = 0.10
    min_fade_frames: int = 5
    max_fade_frames: int = 30

    # --------------------------------------------------------
    # Numerical stability
    # --------------------------------------------------------
    eps: float = 1e-8


def ema_smooth_1d(x: np.ndarray, alpha: float = 0.25) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if len(x) == 0:
        return x.astype(np.float32)

    y = np.zeros_like(x, dtype=np.float32)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = alpha * x[i] + (1.0 - alpha) * y[i - 1]
    return y.astype(np.float32)


def safe_mean_std(x: np.ndarray, eps: float = 1e-8) -> Tuple[float, float]:
    x = np.asarray(x, dtype=np.float32)
    mean_val = float(np.mean(x))
    std_val = float(np.std(x))
    if std_val < eps:
        std_val = 1.0
    return mean_val, std_val


def build_fade_envelope(
    n_frames: int,
    fade_ratio: float = 0.10,
    min_fade_frames: int = 5,
    max_fade_frames: int = 30,
) -> np.ndarray:
    """
    Build a cosine fade-in / fade-out envelope:
      - starts at 0
      - rises smoothly to 1
      - stays at 1 in the middle
      - falls smoothly back to 0 at the end
    """
    if n_frames <= 0:
        return np.zeros((0,), dtype=np.float32)

    if n_frames == 1:
        return np.zeros((1,), dtype=np.float32)

    fade_len = int(round(n_frames * fade_ratio))
    fade_len = max(min_fade_frames, fade_len)
    fade_len = min(max_fade_frames, fade_len)

    # Prevent overlap from becoming too aggressive on short sequences
    fade_len = min(fade_len, n_frames // 2)

    env = np.ones(n_frames, dtype=np.float32)

    if fade_len <= 0:
        env[0] = 0.0
        env[-1] = 0.0
        return env

    # Cosine fade from 0 -> 1
    t = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
    fade_in = 0.5 - 0.5 * np.cos(np.pi * t)
    fade_out = fade_in[::-1].copy()

    env[:fade_len] = fade_in
    env[-fade_len:] = np.minimum(env[-fade_len:], fade_out)

    # Force exact zeros at both ends
    env[0] = 0.0
    env[-1] = 0.0

    return env.astype(np.float32)


def compute_reference_stats(
    df_motion: pd.DataFrame,
    cfg: HeadAngleConfig,
) -> Dict[str, float]:
    required_cols = ["ear_vec_y", "mid_ear_to_nose_z"]
    for c in required_cols:
        if c not in df_motion.columns:
            raise KeyError(f"Missing column in motion dataframe: {c}")

    ear_vec_y = df_motion["ear_vec_y"].to_numpy(dtype=np.float32)
    mid_ear_to_nose_z = df_motion["mid_ear_to_nose_z"].to_numpy(dtype=np.float32)

    ear_mean, ear_std = safe_mean_std(ear_vec_y, eps=cfg.eps)
    nose_mean, nose_std = safe_mean_std(mid_ear_to_nose_z, eps=cfg.eps)

    return {
        "ear_vec_y_mean": ear_mean,
        "ear_vec_y_std": ear_std,
        "mid_ear_to_nose_z_mean": nose_mean,
        "mid_ear_to_nose_z_std": nose_std,
    }


def scalar_to_roll(
    ear_vec_y_value: float,
    ear_vec_y_mean: float,
    ear_vec_y_std: float,
    cfg: HeadAngleConfig,
) -> float:
    roll_deg = ((float(ear_vec_y_value) - ear_vec_y_mean) / (2.0 * ear_vec_y_std)) * cfg.roll_angle_range_deg
    roll_deg = cfg.roll_sign * roll_deg + cfg.roll_offset_deg
    roll_deg = float(np.clip(roll_deg, cfg.roll_min_deg, cfg.roll_max_deg))
    return roll_deg


def scalar_to_yaw(
    mid_ear_to_nose_z_value: float,
    mid_ear_to_nose_z_mean: float,
    mid_ear_to_nose_z_std: float,
    cfg: HeadAngleConfig,
) -> float:
    yaw_deg = (
        (float(mid_ear_to_nose_z_value) - mid_ear_to_nose_z_mean)
        / (2.0 * mid_ear_to_nose_z_std)
    ) * cfg.yaw_angle_range_deg
    yaw_deg = cfg.yaw_sign * yaw_deg + cfg.yaw_offset_deg
    yaw_deg = float(np.clip(yaw_deg, cfg.yaw_min_deg, cfg.yaw_max_deg))
    return yaw_deg


def add_roll_yaw_to_motion_df(
    df_motion: pd.DataFrame,
    cfg: HeadAngleConfig | None = None,
) -> pd.DataFrame:
    if cfg is None:
        cfg = HeadAngleConfig()

    required_cols = ["ear_vec_y", "mid_ear_to_nose_z"]
    for c in required_cols:
        if c not in df_motion.columns:
            raise KeyError(f"Missing column in motion dataframe: {c}")

    stats = compute_reference_stats(df_motion, cfg)

    roll_list = []
    yaw_list = []

    ear_vec_y_arr = df_motion["ear_vec_y"].to_numpy(dtype=np.float32)
    mid_ear_to_nose_z_arr = df_motion["mid_ear_to_nose_z"].to_numpy(dtype=np.float32)

    for ear_vec_y_value, mid_ear_to_nose_z_value in zip(ear_vec_y_arr, mid_ear_to_nose_z_arr):
        roll_deg = scalar_to_roll(
            ear_vec_y_value=ear_vec_y_value,
            ear_vec_y_mean=stats["ear_vec_y_mean"],
            ear_vec_y_std=stats["ear_vec_y_std"],
            cfg=cfg,
        )
        yaw_deg = scalar_to_yaw(
            mid_ear_to_nose_z_value=mid_ear_to_nose_z_value,
            mid_ear_to_nose_z_mean=stats["mid_ear_to_nose_z_mean"],
            mid_ear_to_nose_z_std=stats["mid_ear_to_nose_z_std"],
            cfg=cfg,
        )

        roll_list.append(roll_deg)
        yaw_list.append(yaw_deg)

    roll_arr = np.asarray(roll_list, dtype=np.float32)
    yaw_arr = np.asarray(yaw_list, dtype=np.float32)

    if cfg.smooth_alpha > 0:
        roll_arr = ema_smooth_1d(roll_arr, alpha=cfg.smooth_alpha)
        yaw_arr = ema_smooth_1d(yaw_arr, alpha=cfg.smooth_alpha)

    if cfg.use_fade_envelope:
        envelope = build_fade_envelope(
            n_frames=len(roll_arr),
            fade_ratio=cfg.fade_ratio,
            min_fade_frames=cfg.min_fade_frames,
            max_fade_frames=cfg.max_fade_frames,
        )
        roll_arr = roll_arr * envelope
        yaw_arr = yaw_arr * envelope
    else:
        envelope = np.ones(len(roll_arr), dtype=np.float32)

    df_out = df_motion.copy()
    df_out["roll"] = roll_arr
    df_out["yaw"] = yaw_arr

    # Optional debug columns
    df_out["ear_vec_y_mean_used"] = np.float32(stats["ear_vec_y_mean"])
    df_out["ear_vec_y_std_used"] = np.float32(stats["ear_vec_y_std"])
    df_out["mid_ear_to_nose_z_mean_used"] = np.float32(stats["mid_ear_to_nose_z_mean"])
    df_out["mid_ear_to_nose_z_std_used"] = np.float32(stats["mid_ear_to_nose_z_std"])
    df_out["fade_envelope"] = envelope.astype(np.float32)

    return df_out