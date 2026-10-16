# lip_dist_from_motion_v1.py
# ============================================================
# Convert motion features to normalized lip-control values in [0, 1]
#
# Target outputs:
#   - lip_open_dist_3d
#   - mouth_width_dist_3d
#   - upper_lip_thickness_3d
#   - lower_lip_thickness_3d
#
# Mapping rule for each target:
#   normalized_scalar = (val - mean) / (2 * std)
#
# Then:
#   1) optional sign / offset
#   2) clip to a configurable raw range
#   3) scale raw range to [0, 1]
#   4) optional EMA smoothing
#   5) apply fade-in / fade-out envelope so the motion starts
#      from 0 and returns to 0 at the end
#
# Mean and standard deviation are computed from the input
# dataframe itself, exactly like the head-angle style pipeline.
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class LipDistConfig:
    # --------------------------------------------------------
    # Required source columns in df_motion
    # These are also used as output column names.
    # --------------------------------------------------------
    lip_open_col: str = "lip_open_dist_3d"
    mouth_width_col: str = "mouth_width_dist_3d"
    upper_lip_col: str = "upper_lip_thickness_3d"
    lower_lip_col: str = "lower_lip_thickness_3d"

    # --------------------------------------------------------
    # Raw normalized range before scaling to [0, 1]
    #
    # raw = (val - mean) / (2 * std)
    #
    # Then clip raw into [raw_min, raw_max]
    # Then map to [0, 1]
    #
    # Keeping symmetric range is usually the cleanest choice.
    # --------------------------------------------------------
    raw_min: float = -1.0
    raw_max: float = 1.0

    # --------------------------------------------------------
    # Optional sign / offset per channel
    # Useful if one channel needs inversion or shift.
    # --------------------------------------------------------
    lip_open_sign: float = 1.0
    mouth_width_sign: float = 1.0
    upper_lip_sign: float = 1.0
    lower_lip_sign: float = 1.0

    lip_open_offset: float = 0.0
    mouth_width_offset: float = 0.0
    upper_lip_offset: float = 0.0
    lower_lip_offset: float = 0.0

    # --------------------------------------------------------
    # Final smoothing on output values after scaling to [0, 1]
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

    # Prevent the two sides from overlapping too aggressively
    fade_len = min(fade_len, n_frames // 2)

    env = np.ones(n_frames, dtype=np.float32)

    if fade_len <= 0:
        env[0] = 0.0
        env[-1] = 0.0
        return env

    t = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
    fade_in = 0.5 - 0.5 * np.cos(np.pi * t)
    fade_out = fade_in[::-1].copy()

    env[:fade_len] = fade_in
    env[-fade_len:] = np.minimum(env[-fade_len:], fade_out)

    # Force exact zeros at both ends
    env[0] = 0.0
    env[-1] = 0.0

    return env.astype(np.float32)


def clip_and_scale_to_unit(
    x: np.ndarray,
    raw_min: float,
    raw_max: float,
    eps: float = 1e-8,
) -> np.ndarray:
    """
    Clip x to [raw_min, raw_max], then linearly scale to [0, 1].
    """
    x = np.asarray(x, dtype=np.float32)

    if raw_max - raw_min < eps:
        raise ValueError("raw_max must be larger than raw_min.")

    x = np.clip(x, raw_min, raw_max)
    x = (x - raw_min) / (raw_max - raw_min)
    x = np.clip(x, 0.0, 1.0)
    return x.astype(np.float32)


def compute_reference_stats(
    df_motion: pd.DataFrame,
    cfg: LipDistConfig,
) -> Dict[str, float]:
    required_cols = [
        cfg.lip_open_col,
        cfg.mouth_width_col,
        cfg.upper_lip_col,
        cfg.lower_lip_col,
    ]
    for c in required_cols:
        if c not in df_motion.columns:
            raise KeyError(f"Missing column in motion dataframe: {c}")

    lip_open = df_motion[cfg.lip_open_col].to_numpy(dtype=np.float32)
    mouth_width = df_motion[cfg.mouth_width_col].to_numpy(dtype=np.float32)
    upper_lip = df_motion[cfg.upper_lip_col].to_numpy(dtype=np.float32)
    lower_lip = df_motion[cfg.lower_lip_col].to_numpy(dtype=np.float32)

    lip_open_mean, lip_open_std = safe_mean_std(lip_open, eps=cfg.eps)
    mouth_width_mean, mouth_width_std = safe_mean_std(mouth_width, eps=cfg.eps)
    upper_lip_mean, upper_lip_std = safe_mean_std(upper_lip, eps=cfg.eps)
    lower_lip_mean, lower_lip_std = safe_mean_std(lower_lip, eps=cfg.eps)

    return {
        f"{cfg.lip_open_col}_mean": lip_open_mean,
        f"{cfg.lip_open_col}_std": lip_open_std,
        f"{cfg.mouth_width_col}_mean": mouth_width_mean,
        f"{cfg.mouth_width_col}_std": mouth_width_std,
        f"{cfg.upper_lip_col}_mean": upper_lip_mean,
        f"{cfg.upper_lip_col}_std": upper_lip_std,
        f"{cfg.lower_lip_col}_mean": lower_lip_mean,
        f"{cfg.lower_lip_col}_std": lower_lip_std,
    }


def scalar_to_unit_value(
    value: float,
    mean_value: float,
    std_value: float,
    sign: float,
    offset: float,
    cfg: LipDistConfig,
) -> float:
    raw = (float(value) - float(mean_value)) / (1.0 * float(std_value))
    raw = float(sign) * raw + float(offset)

    scaled = (np.clip(raw, cfg.raw_min, cfg.raw_max) - cfg.raw_min) / (cfg.raw_max - cfg.raw_min)
    scaled = float(np.clip(scaled, 0.0, 1.0))
    return scaled


def add_lip_dist_to_motion_df(
    df_motion: pd.DataFrame,
    cfg: LipDistConfig | None = None,
) -> pd.DataFrame:
    if cfg is None:
        cfg = LipDistConfig()

    required_cols = [
        cfg.lip_open_col,
        cfg.mouth_width_col,
        cfg.upper_lip_col,
        cfg.lower_lip_col,
    ]
    for c in required_cols:
        if c not in df_motion.columns:
            raise KeyError(f"Missing column in motion dataframe: {c}")

    stats = compute_reference_stats(df_motion, cfg)

    lip_open_arr_src = df_motion[cfg.lip_open_col].to_numpy(dtype=np.float32)
    mouth_width_arr_src = df_motion[cfg.mouth_width_col].to_numpy(dtype=np.float32)
    upper_lip_arr_src = df_motion[cfg.upper_lip_col].to_numpy(dtype=np.float32)
    lower_lip_arr_src = df_motion[cfg.lower_lip_col].to_numpy(dtype=np.float32)

    lip_open_list = []
    mouth_width_list = []
    upper_lip_list = []
    lower_lip_list = []

    for lip_open_val, mouth_width_val, upper_lip_val, lower_lip_val in zip(
        lip_open_arr_src,
        mouth_width_arr_src,
        upper_lip_arr_src,
        lower_lip_arr_src,
    ):
        lip_open_out = scalar_to_unit_value(
            value=lip_open_val,
            mean_value=stats[f"{cfg.lip_open_col}_mean"],
            std_value=stats[f"{cfg.lip_open_col}_std"],
            sign=cfg.lip_open_sign,
            offset=cfg.lip_open_offset,
            cfg=cfg,
        )
        mouth_width_out = scalar_to_unit_value(
            value=mouth_width_val,
            mean_value=stats[f"{cfg.mouth_width_col}_mean"],
            std_value=stats[f"{cfg.mouth_width_col}_std"],
            sign=cfg.mouth_width_sign,
            offset=cfg.mouth_width_offset,
            cfg=cfg,
        )
        upper_lip_out = scalar_to_unit_value(
            value=upper_lip_val,
            mean_value=stats[f"{cfg.upper_lip_col}_mean"],
            std_value=stats[f"{cfg.upper_lip_col}_std"],
            sign=cfg.upper_lip_sign,
            offset=cfg.upper_lip_offset,
            cfg=cfg,
        )
        lower_lip_out = scalar_to_unit_value(
            value=lower_lip_val,
            mean_value=stats[f"{cfg.lower_lip_col}_mean"],
            std_value=stats[f"{cfg.lower_lip_col}_std"],
            sign=cfg.lower_lip_sign,
            offset=cfg.lower_lip_offset,
            cfg=cfg,
        )

        lip_open_list.append(lip_open_out)
        mouth_width_list.append(mouth_width_out)
        upper_lip_list.append(upper_lip_out)
        lower_lip_list.append(lower_lip_out)

    lip_open_arr = np.asarray(lip_open_list, dtype=np.float32)
    mouth_width_arr = np.asarray(mouth_width_list, dtype=np.float32)
    upper_lip_arr = np.asarray(upper_lip_list, dtype=np.float32)
    lower_lip_arr = np.asarray(lower_lip_list, dtype=np.float32)

    if cfg.smooth_alpha > 0:
        lip_open_arr = ema_smooth_1d(lip_open_arr, alpha=cfg.smooth_alpha)
        mouth_width_arr = ema_smooth_1d(mouth_width_arr, alpha=cfg.smooth_alpha)
        upper_lip_arr = ema_smooth_1d(upper_lip_arr, alpha=cfg.smooth_alpha)
        lower_lip_arr = ema_smooth_1d(lower_lip_arr, alpha=cfg.smooth_alpha)

    if cfg.use_fade_envelope:
        envelope = build_fade_envelope(
            n_frames=len(lip_open_arr),
            fade_ratio=cfg.fade_ratio,
            min_fade_frames=cfg.min_fade_frames,
            max_fade_frames=cfg.max_fade_frames,
        )
        lip_open_arr = lip_open_arr * envelope
        mouth_width_arr = mouth_width_arr * envelope
        upper_lip_arr = upper_lip_arr * envelope
        lower_lip_arr = lower_lip_arr * envelope
    else:
        envelope = np.ones(len(lip_open_arr), dtype=np.float32)

    # Final safety clamp after smoothing and fade
    lip_open_arr = np.clip(lip_open_arr, 0.0, 1.0).astype(np.float32)
    mouth_width_arr = np.clip(mouth_width_arr, 0.0, 1.0).astype(np.float32)
    upper_lip_arr = np.clip(upper_lip_arr, 0.0, 1.0).astype(np.float32)
    lower_lip_arr = np.clip(lower_lip_arr, 0.0, 1.0).astype(np.float32)

    df_out = df_motion.copy()

    # Overwrite the four target columns with normalized outputs in [0, 1]
    df_out[cfg.lip_open_col] = lip_open_arr
    df_out[cfg.mouth_width_col] = mouth_width_arr
    df_out[cfg.upper_lip_col] = upper_lip_arr
    df_out[cfg.lower_lip_col] = lower_lip_arr

    # Optional debug columns
    df_out[f"{cfg.lip_open_col}_mean_used"] = np.float32(stats[f"{cfg.lip_open_col}_mean"])
    df_out[f"{cfg.lip_open_col}_std_used"] = np.float32(stats[f"{cfg.lip_open_col}_std"])

    df_out[f"{cfg.mouth_width_col}_mean_used"] = np.float32(stats[f"{cfg.mouth_width_col}_mean"])
    df_out[f"{cfg.mouth_width_col}_std_used"] = np.float32(stats[f"{cfg.mouth_width_col}_std"])

    df_out[f"{cfg.upper_lip_col}_mean_used"] = np.float32(stats[f"{cfg.upper_lip_col}_mean"])
    df_out[f"{cfg.upper_lip_col}_std_used"] = np.float32(stats[f"{cfg.upper_lip_col}_std"])

    df_out[f"{cfg.lower_lip_col}_mean_used"] = np.float32(stats[f"{cfg.lower_lip_col}_mean"])
    df_out[f"{cfg.lower_lip_col}_std_used"] = np.float32(stats[f"{cfg.lower_lip_col}_std"])

    df_out["fade_envelope"] = envelope.astype(np.float32)

    return df_out


if __name__ == "__main__":
    # Example usage
    df_example = pd.DataFrame(
        {
            "lip_open_dist_3d": [1.0, 1.2, 1.6, 1.4, 1.1, 0.9],
            "mouth_width_dist_3d": [2.0, 2.1, 2.3, 2.4, 2.2, 2.0],
            "upper_lip_thickness_3d": [0.5, 0.55, 0.60, 0.58, 0.53, 0.50],
            "lower_lip_thickness_3d": [0.6, 0.65, 0.72, 0.70, 0.64, 0.61],
        }
    )

    cfg = LipDistConfig(
        raw_min=-1.0,
        raw_max=1.0,
        smooth_alpha=0.25,
        use_fade_envelope=True,
        fade_ratio=0.15,
        min_fade_frames=2,
        max_fade_frames=10,
    )

    df_out = add_lip_dist_to_motion_df(df_example, cfg=cfg)

    print(df_out)