# motion_inference_v3_cpu.py
# ============================================================
# WAV-only inference module
# HYBRID VERSION:
#   - Transformer predicts full 13-dim motion/features
#   - MLP predicts only 4 lip features
#   - Final output keeps old 13-column format
#
# Final lip columns replaced by MLP:
#   - lip_open_dist_3d
#   - mouth_width_dist_3d
#   - upper_lip_thickness_3d
#   - lower_lip_thickness_3d
# ============================================================

from __future__ import annotations

import os
import math
import gc
import pickle
from dataclasses import dataclass
from typing import Tuple, Dict, Optional, List

import numpy as np
import pandas as pd
import librosa

import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================
# CONFIG STRUCTURES
# ============================================================
@dataclass
class TrainConfig:
    data_dir: str = r""
    output_dir: str = r"D:\Virtual officer\outputs_transformer_local_window"

    test_wav_path: Optional[str] = None
    test_excel_time_path: Optional[str] = None
    run_external_test_after_train: bool = True

    time_column: str = "time_sec"
    target_columns: Tuple[str, ...] = (
        "ear_vec_x",
        "ear_vec_y",
        "ear_vec_z",
        "mid_ear_to_nose_x",
        "mid_ear_to_nose_y",
        "mid_ear_to_nose_z",
        "lip_open_dist_3d",
        "mouth_width_dist_3d",
        "upper_lip_thickness_3d",
        "lower_lip_thickness_3d",
        "brow_eye_left_3d",
        "brow_eye_right_3d",
        "brow_eye_mean_3d",
    )

    sr: int = 16000
    dense_n_fft: int = 1024
    dense_win_length: int = 640
    dense_hop_length: int = 160
    n_mels: int = 64
    n_mfcc: int = 13
    fmin: float = 50.0
    fmax: float = 7600.0
    roll_percent: float = 0.85

    use_mel: bool = True
    use_mel_delta: bool = True
    use_mel_delta2: bool = True
    use_pitch: bool = True
    use_pitch_delta: bool = True
    use_energy: bool = True
    use_energy_delta: bool = True
    use_mfcc: bool = True
    use_mfcc_delta: bool = True
    use_mfcc_delta2: bool = True
    use_zcr: bool = True
    use_spectral_centroid: bool = True
    use_spectral_bandwidth: bool = True
    use_spectral_rolloff: bool = True
    use_spectral_flatness: bool = True
    use_voiced_flag: bool = True

    batch_size: int = 1
    max_audio_frames: Optional[int] = 4000
    max_excel_steps: Optional[int] = 500

    history_length: int = 10
    audio_window_sec: float = 0.8
    max_audio_window_frames: int = 120

    d_model: int = 256
    nhead: int = 8
    num_audio_encoder_layers: int = 4
    num_decoder_layers: int = 4
    dim_feedforward: int = 512
    dropout: float = 0.1

    num_epochs: int = 60
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    grad_clip: float = 1.0
    train_ratio: float = 0.8
    random_seed: int = 42
    num_workers: int = 0

    pos_loss_weight: float = 1.0
    vel_loss_weight: float = 0.5

    pred_smoothing_alpha: float = 0.25

    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class LipMLPConfig:
    data_dir: str = r""
    output_dir: str = r"./outputs_lip_mlp_local_window"

    test_wav_path: Optional[str] = None
    test_excel_time_path: Optional[str] = None
    run_external_test_after_train: bool = True

    time_column: str = "time_sec"
    target_columns: Tuple[str, ...] = (
        "lip_open_dist_3d",
        "mouth_width_dist_3d",
        "upper_lip_thickness_3d",
        "lower_lip_thickness_3d",
    )

    sr: int = 16000
    dense_n_fft: int = 1024
    dense_win_length: int = 640
    dense_hop_length: int = 160
    n_mels: int = 64
    n_mfcc: int = 13
    fmin: float = 50.0
    fmax: float = 7600.0
    roll_percent: float = 0.85

    use_mel: bool = True
    use_mel_delta: bool = True
    use_mel_delta2: bool = True
    use_pitch: bool = True
    use_pitch_delta: bool = True
    use_energy: bool = True
    use_energy_delta: bool = True
    use_mfcc: bool = True
    use_mfcc_delta: bool = True
    use_mfcc_delta2: bool = True
    use_zcr: bool = True
    use_spectral_centroid: bool = True
    use_spectral_bandwidth: bool = True
    use_spectral_rolloff: bool = True
    use_spectral_flatness: bool = True
    use_voiced_flag: bool = True

    batch_size: int = 1
    max_audio_frames: Optional[int] = 4000
    max_excel_steps: Optional[int] = 500

    history_length: int = 10
    audio_window_sec: float = 0.8
    max_audio_window_frames: int = 120

    hidden_dims: Tuple[int, ...] = (512, 256, 128)
    dropout: float = 0.2

    num_epochs: int = 100
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    grad_clip: float = 1.0
    train_ratio: float = 0.8
    random_seed: int = 42
    num_workers: int = 0

    pos_loss_weight: float = 1.0
    vel_loss_weight: float = 0.5

    pred_smoothing_alpha: float = 0.25

    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# ============================================================
# BASIC UTILS
# ============================================================
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def strip_ext(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def load_pickle(path: str):
    with open(path, "rb") as f:
        return pickle.load(f)


def cleanup_torch_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def ema_smooth(x: np.ndarray, alpha: float = 0.25) -> np.ndarray:
    if len(x) == 0:
        return x
    y = np.zeros_like(x)
    y[0] = x[0]
    for t in range(1, len(x)):
        y[t] = alpha * x[t] + (1.0 - alpha) * y[t - 1]
    return y


def assert_np_finite(name: str, x: np.ndarray) -> None:
    if not np.isfinite(x).all():
        bad = np.argwhere(~np.isfinite(x))
        raise RuntimeError(f"{name} contains NaN/Inf. First bad indices: {bad[:10]}")


def assert_torch_finite(name: str, x: torch.Tensor) -> None:
    if not torch.isfinite(x).all():
        raise RuntimeError(f"{name} contains NaN/Inf")


class StandardScalerNP:
    def __init__(self):
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None

    def fit(self, x: np.ndarray) -> None:
        self.mean_ = np.mean(x, axis=0)
        self.std_ = np.std(x, axis=0)
        self.std_[self.std_ < 1e-8] = 1.0

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean_) / self.std_

    def inverse_transform(self, x: np.ndarray) -> np.ndarray:
        return x * self.std_ + self.mean_

    def load_state_dict(self, state: Dict) -> None:
        self.mean_ = state["mean"]
        self.std_ = state["std"]


class MinMaxScalerNP:
    def __init__(self):
        self.min_: Optional[np.ndarray] = None
        self.max_: Optional[np.ndarray] = None
        self.range_: Optional[np.ndarray] = None

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.min_) / self.range_

    def inverse_transform(self, x: np.ndarray) -> np.ndarray:
        return x * self.range_ + self.min_

    def load_state_dict(self, state: Dict) -> None:
        self.min_ = state["min"]
        self.max_ = state["max"]
        self.range_ = state["range"]


# ============================================================
# AUDIO FEATURES
# ============================================================
def safe_delta(feat: np.ndarray, width: int = 9, order: int = 1) -> np.ndarray:
    T = feat.shape[1]
    if T < 3:
        return np.zeros_like(feat, dtype=np.float32)

    width = min(width, T if T % 2 == 1 else T - 1)
    if width < 3:
        width = 3
    if width % 2 == 0:
        width -= 1
    if width < 3:
        return np.zeros_like(feat, dtype=np.float32)

    out = librosa.feature.delta(feat, width=width, order=order)
    return out.astype(np.float32)


def extract_dense_audio_features(
    wav_path: str,
    cfg,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    y, sr = librosa.load(wav_path, sr=cfg.sr, mono=True)

    feat_blocks = []
    feat_names = []

    mel = librosa.feature.melspectrogram(
        y=y,
        sr=sr,
        n_fft=cfg.dense_n_fft,
        hop_length=cfg.dense_hop_length,
        win_length=cfg.dense_win_length,
        n_mels=cfg.n_mels,
        fmin=cfg.fmin,
        fmax=cfg.fmax,
        power=2.0,
        center=True,
    )
    log_mel = librosa.power_to_db(mel + 1e-10).astype(np.float32)

    if cfg.use_mel:
        feat_blocks.append(log_mel.T)
        feat_names += [f"mel_{i}" for i in range(cfg.n_mels)]

    if cfg.use_mel_delta:
        mel_d1 = safe_delta(log_mel, order=1)
        feat_blocks.append(mel_d1.T)
        feat_names += [f"mel_d1_{i}" for i in range(cfg.n_mels)]

    if cfg.use_mel_delta2:
        mel_d2 = safe_delta(log_mel, order=2)
        feat_blocks.append(mel_d2.T)
        feat_names += [f"mel_d2_{i}" for i in range(cfg.n_mels)]

    f0 = librosa.yin(
        y,
        fmin=50,
        fmax=500,
        sr=sr,
        frame_length=cfg.dense_n_fft,
        hop_length=cfg.dense_hop_length,
    )
    f0 = np.asarray(f0, dtype=np.float32)
    voiced_flag = np.isfinite(f0).astype(np.float32)
    f0 = np.nan_to_num(f0, nan=0.0, posinf=0.0, neginf=0.0)
    log_f0 = np.log1p(f0).reshape(1, -1).astype(np.float32)

    if cfg.use_pitch:
        feat_blocks.append(log_f0.T)
        feat_names += ["log_f0"]

    if cfg.use_pitch_delta:
        f0_d1 = safe_delta(log_f0, order=1)
        feat_blocks.append(f0_d1.T)
        feat_names += ["log_f0_d1"]

    if cfg.use_voiced_flag:
        feat_blocks.append(voiced_flag.reshape(-1, 1))
        feat_names += ["voiced_flag"]

    rms = librosa.feature.rms(
        y=y,
        frame_length=cfg.dense_n_fft,
        hop_length=cfg.dense_hop_length,
        center=True,
    ).astype(np.float32)

    if cfg.use_energy:
        feat_blocks.append(rms.T)
        feat_names += ["rms"]

    if cfg.use_energy_delta:
        rms_d1 = safe_delta(rms, order=1)
        feat_blocks.append(rms_d1.T)
        feat_names += ["rms_d1"]

    if cfg.use_mfcc or cfg.use_mfcc_delta or cfg.use_mfcc_delta2:
        mfcc = librosa.feature.mfcc(S=log_mel, n_mfcc=cfg.n_mfcc).astype(np.float32)

        if cfg.use_mfcc:
            feat_blocks.append(mfcc.T)
            feat_names += [f"mfcc_{i}" for i in range(cfg.n_mfcc)]

        if cfg.use_mfcc_delta:
            mfcc_d1 = safe_delta(mfcc, order=1)
            feat_blocks.append(mfcc_d1.T)
            feat_names += [f"mfcc_d1_{i}" for i in range(cfg.n_mfcc)]

        if cfg.use_mfcc_delta2:
            mfcc_d2 = safe_delta(mfcc, order=2)
            feat_blocks.append(mfcc_d2.T)
            feat_names += [f"mfcc_d2_{i}" for i in range(cfg.n_mfcc)]

    spec_blocks = []
    spec_names = []

    if cfg.use_zcr:
        zcr = librosa.feature.zero_crossing_rate(
            y,
            frame_length=cfg.dense_n_fft,
            hop_length=cfg.dense_hop_length,
            center=True,
        ).astype(np.float32).T
        spec_blocks.append(zcr)
        spec_names += ["zcr"]

    if cfg.use_spectral_centroid:
        centroid = librosa.feature.spectral_centroid(
            y=y,
            sr=sr,
            n_fft=cfg.dense_n_fft,
            hop_length=cfg.dense_hop_length,
        ).astype(np.float32).T
        spec_blocks.append(centroid)
        spec_names += ["spectral_centroid"]

    if cfg.use_spectral_bandwidth:
        bandwidth = librosa.feature.spectral_bandwidth(
            y=y,
            sr=sr,
            n_fft=cfg.dense_n_fft,
            hop_length=cfg.dense_hop_length,
        ).astype(np.float32).T
        spec_blocks.append(bandwidth)
        spec_names += ["spectral_bandwidth"]

    if cfg.use_spectral_rolloff:
        rolloff = librosa.feature.spectral_rolloff(
            y=y,
            sr=sr,
            n_fft=cfg.dense_n_fft,
            hop_length=cfg.dense_hop_length,
            roll_percent=cfg.roll_percent,
        ).astype(np.float32).T
        spec_blocks.append(rolloff)
        spec_names += ["spectral_rolloff"]

    if cfg.use_spectral_flatness:
        flatness = librosa.feature.spectral_flatness(
            y=y,
            n_fft=cfg.dense_n_fft,
            hop_length=cfg.dense_hop_length,
        ).astype(np.float32).T
        spec_blocks.append(flatness)
        spec_names += ["spectral_flatness"]

    if len(spec_blocks) > 0:
        feat_blocks.append(np.concatenate(spec_blocks, axis=1))
        feat_names += spec_names

    if len(feat_blocks) == 0:
        raise ValueError("No audio features enabled.")

    min_T = min(block.shape[0] for block in feat_blocks)
    feat_blocks = [block[:min_T].astype(np.float32) for block in feat_blocks]

    dense_feats = np.concatenate(feat_blocks, axis=1).astype(np.float32)
    dense_times = librosa.frames_to_time(
        np.arange(min_T),
        sr=sr,
        hop_length=cfg.dense_hop_length,
        n_fft=None,
    ).astype(np.float32)

    dense_feats = np.nan_to_num(dense_feats, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    dense_times = np.nan_to_num(dense_times, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    assert_np_finite("dense_feats", dense_feats)
    assert_np_finite("dense_times", dense_times)

    return dense_times, dense_feats, feat_names


# ============================================================
# TRANSFORMER MODEL
# ============================================================
class SinusoidalPositionalEncoding(nn.Module):
    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 2000):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        self.d_model = d_model
        self.register_buffer("pe", self._build_pe(max_len, d_model), persistent=False)

    @staticmethod
    def _build_pe(max_len: int, d_model: int) -> torch.Tensor:
        pe = torch.zeros(max_len, d_model, dtype=torch.float32)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term[:pe[:, 1::2].shape[1]])
        return pe.unsqueeze(0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        T = x.shape[1]
        if T > self.pe.shape[1]:
            self.pe = self._build_pe(T, self.d_model).to(x.device)
        x = x + self.pe[:, :T]
        return self.dropout(x)


class CustomTransformerDecoderLayer(nn.Module):
    def __init__(
        self,
        d_model: int,
        nhead: int,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=nhead,
            dropout=dropout,
            batch_first=True,
        )
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=nhead,
            dropout=dropout,
            batch_first=True,
        )
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.linear2 = nn.Linear(dim_feedforward, d_model)

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)

        self.dropout = nn.Dropout(dropout)
        self.dropout_ff = nn.Dropout(dropout)

    def forward_no_pad_mask(
        self,
        tgt: torch.Tensor,
        memory: torch.Tensor,
        self_attn_mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        x = tgt

        x2, _ = self.self_attn(
            query=x,
            key=x,
            value=x,
            attn_mask=self_attn_mask,
            need_weights=False,
        )
        x = self.norm1(x + self.dropout(x2))

        x2, _ = self.cross_attn(
            query=x,
            key=memory,
            value=memory,
            need_weights=False,
        )
        x = self.norm2(x + self.dropout(x2))

        x2 = self.linear2(self.dropout_ff(F.relu(self.linear1(x))))
        x = self.norm3(x + self.dropout(x2))
        return x


class LocalSpeechToMotionTransformer(nn.Module):
    def __init__(
        self,
        audio_input_dim: int,
        target_dim: int,
        history_length: int = 10,
        d_model: int = 256,
        nhead: int = 8,
        num_audio_encoder_layers: int = 4,
        num_decoder_layers: int = 4,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.history_length = history_length
        self.d_model = d_model
        self.target_dim = target_dim

        self.audio_in_proj = nn.Linear(audio_input_dim, d_model)
        self.motion_in_proj = nn.Linear(target_dim, d_model)

        self.audio_pos_enc = SinusoidalPositionalEncoding(d_model, dropout=dropout)
        self.motion_pos_enc = SinusoidalPositionalEncoding(d_model, dropout=dropout)

        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            norm_first=False,
        )
        self.audio_encoder = nn.TransformerEncoder(
            enc_layer,
            num_layers=num_audio_encoder_layers,
        )

        self.decoder_layers = nn.ModuleList([
            CustomTransformerDecoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
            )
            for _ in range(num_decoder_layers)
        ])

        self.out_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, target_dim),
        )

    def build_causal_mask(self, T: int, device: torch.device) -> torch.Tensor:
        return torch.triu(torch.ones(T, T, device=device, dtype=torch.bool), diagonal=1)

    def forward_infer_single(
        self,
        audio_window_x: torch.Tensor,
        motion_history: torch.Tensor,
    ) -> torch.Tensor:
        audio_emb = self.audio_in_proj(audio_window_x) * math.sqrt(self.d_model)
        motion_emb = self.motion_in_proj(motion_history) * math.sqrt(self.d_model)

        assert_torch_finite("audio_emb after proj", audio_emb)
        assert_torch_finite("motion_emb after proj", motion_emb)

        audio_emb = self.audio_pos_enc(audio_emb)
        motion_emb = self.motion_pos_enc(motion_emb)

        assert_torch_finite("audio_emb after pos", audio_emb)
        assert_torch_finite("motion_emb after pos", motion_emb)

        memory = self.audio_encoder(audio_emb)
        assert_torch_finite("memory after audio_encoder", memory)

        causal_mask = self.build_causal_mask(motion_emb.shape[1], device=motion_emb.device)

        x = motion_emb
        for i, layer in enumerate(self.decoder_layers):
            x = layer.forward_no_pad_mask(
                tgt=x,
                memory=memory,
                self_attn_mask=causal_mask,
            )
            assert_torch_finite(f"decoder layer {i} output", x)

        out_seq = self.out_head(x)
        assert_torch_finite("out_seq", out_seq)

        next_pred = out_seq[:, -1, :]
        assert_torch_finite("next_pred", next_pred)
        return next_pred


# ============================================================
# LIP MLP MODEL
# ============================================================
class LipMLPLocalWindow(nn.Module):
    def __init__(
        self,
        audio_input_dim: int,
        target_dim: int,
        history_length: int,
        audio_window_frames: int,
        hidden_dims: Tuple[int, ...] = (512, 256, 128),
        dropout: float = 0.2,
    ):
        super().__init__()
        self.audio_input_dim = audio_input_dim
        self.target_dim = target_dim
        self.history_length = history_length
        self.audio_window_frames = audio_window_frames

        input_dim = audio_window_frames * audio_input_dim + history_length * target_dim

        layers = []
        prev_dim = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev_dim, h))
            layers.append(nn.LayerNorm(h))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
            prev_dim = h

        layers.append(nn.Linear(prev_dim, target_dim))
        self.net = nn.Sequential(*layers)

    def forward(
        self,
        audio_window_x: torch.Tensor,   # [B, K, F]
        motion_history: torch.Tensor,   # [B, H, D]
    ) -> torch.Tensor:
        B = audio_window_x.shape[0]
        x_audio = audio_window_x.reshape(B, -1)
        x_hist = motion_history.reshape(B, -1)
        x = torch.cat([x_audio, x_hist], dim=1)
        out = self.net(x)
        out = torch.sigmoid(out)
        return out


# ============================================================
# LOAD MODELS + SCALERS
# ============================================================
def load_transformer_model_and_scalers(model_dir: str, device: Optional[str] = None):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    best_model_path = os.path.join(model_dir, "best_model.pt")
    audio_scaler_path = os.path.join(model_dir, "audio_scaler.pkl")
    y_scaler_path = os.path.join(model_dir, "y_scaler.pkl")

    if not os.path.isfile(best_model_path):
        raise FileNotFoundError(f"Transformer best_model.pt not found: {best_model_path}")
    if not os.path.isfile(audio_scaler_path):
        raise FileNotFoundError(f"Transformer audio_scaler.pkl not found: {audio_scaler_path}")
    if not os.path.isfile(y_scaler_path):
        raise FileNotFoundError(f"Transformer y_scaler.pkl not found: {y_scaler_path}")

    ckpt = torch.load(best_model_path, map_location=device)
    saved_cfg = TrainConfig(**ckpt["cfg"])

    model = LocalSpeechToMotionTransformer(
        audio_input_dim=ckpt["audio_input_dim"],
        target_dim=ckpt["target_dim"],
        history_length=saved_cfg.history_length,
        d_model=saved_cfg.d_model,
        nhead=saved_cfg.nhead,
        num_audio_encoder_layers=saved_cfg.num_audio_encoder_layers,
        num_decoder_layers=saved_cfg.num_decoder_layers,
        dim_feedforward=saved_cfg.dim_feedforward,
        dropout=saved_cfg.dropout,
    ).to(device)

    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    audio_scaler = StandardScalerNP()
    y_scaler = StandardScalerNP()
    audio_scaler.load_state_dict(load_pickle(audio_scaler_path))
    y_scaler.load_state_dict(load_pickle(y_scaler_path))

    assert_np_finite("transformer audio_scaler.mean_", audio_scaler.mean_)
    assert_np_finite("transformer audio_scaler.std_", audio_scaler.std_)
    assert_np_finite("transformer y_scaler.mean_", y_scaler.mean_)
    assert_np_finite("transformer y_scaler.std_", y_scaler.std_)

    for name, p in model.named_parameters():
        if not torch.isfinite(p).all():
            raise RuntimeError(f"Transformer model parameter has NaN/Inf: {name}")

    return model, audio_scaler, y_scaler, saved_cfg


def load_lip_mlp_model_and_scalers(model_dir: str, device: Optional[str] = None):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    best_model_path = os.path.join(model_dir, "best_model.pt")
    audio_scaler_path = os.path.join(model_dir, "audio_scaler.pkl")
    y_scaler_path = os.path.join(model_dir, "y_scaler.pkl")

    if not os.path.isfile(best_model_path):
        raise FileNotFoundError(f"Lip MLP best_model.pt not found: {best_model_path}")
    if not os.path.isfile(audio_scaler_path):
        raise FileNotFoundError(f"Lip MLP audio_scaler.pkl not found: {audio_scaler_path}")
    if not os.path.isfile(y_scaler_path):
        raise FileNotFoundError(f"Lip MLP y_scaler.pkl not found: {y_scaler_path}")

    ckpt = torch.load(best_model_path, map_location=device)
    saved_cfg = LipMLPConfig(**ckpt["cfg"])

    model = LipMLPLocalWindow(
        audio_input_dim=ckpt["audio_input_dim"],
        target_dim=ckpt["target_dim"],
        history_length=saved_cfg.history_length,
        audio_window_frames=saved_cfg.max_audio_window_frames,
        hidden_dims=tuple(saved_cfg.hidden_dims),
        dropout=saved_cfg.dropout,
    ).to(device)

    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    audio_scaler = StandardScalerNP()
    y_scaler = MinMaxScalerNP()
    audio_scaler.load_state_dict(load_pickle(audio_scaler_path))
    y_scaler.load_state_dict(load_pickle(y_scaler_path))

    assert_np_finite("lip mlp audio_scaler.mean_", audio_scaler.mean_)
    assert_np_finite("lip mlp audio_scaler.std_", audio_scaler.std_)
    assert_np_finite("lip mlp y_scaler.min_", y_scaler.min_)
    assert_np_finite("lip mlp y_scaler.max_", y_scaler.max_)
    assert_np_finite("lip mlp y_scaler.range_", y_scaler.range_)

    for name, p in model.named_parameters():
        if not torch.isfinite(p).all():
            raise RuntimeError(f"Lip MLP model parameter has NaN/Inf: {name}")

    return model, audio_scaler, y_scaler, saved_cfg


# ============================================================
# WINDOW + TIMELINE
# ============================================================
def build_audio_window_single(
    audio_x: np.ndarray,
    audio_times: np.ndarray,
    current_time: float,
    window_sec: float,
    max_audio_window_frames: Optional[int],
) -> np.ndarray:
    t_min = current_time - window_sec
    idx = np.where((audio_times >= t_min) & (audio_times <= current_time))[0]

    if len(idx) == 0:
        prev_idx = np.where(audio_times <= current_time)[0]
        if len(prev_idx) == 0:
            idx = np.array([0], dtype=np.int64)
        else:
            idx = np.array([prev_idx[-1]], dtype=np.int64)

    if max_audio_window_frames is not None and len(idx) > max_audio_window_frames:
        idx = idx[-max_audio_window_frames:]

    win = audio_x[idx]
    assert_np_finite("audio window", win)
    return win.astype(np.float32)


def build_audio_window_single_fixed(
    audio_x: np.ndarray,
    audio_times: np.ndarray,
    current_time: float,
    window_sec: float,
    max_audio_window_frames: int,
) -> np.ndarray:
    K = max_audio_window_frames
    F = audio_x.shape[1]
    out = np.zeros((K, F), dtype=np.float32)

    t_min = current_time - window_sec
    idx = np.where((audio_times >= t_min) & (audio_times <= current_time))[0]

    if len(idx) == 0:
        prev_idx = np.where(audio_times <= current_time)[0]
        if len(prev_idx) == 0:
            idx = np.array([0], dtype=np.int64)
        else:
            idx = np.array([prev_idx[-1]], dtype=np.int64)

    if len(idx) > K:
        idx = idx[-K:]

    seg = audio_x[idx]
    L = seg.shape[0]
    out[K - L:K, :] = seg
    assert_np_finite("fixed audio window", out)
    return out


def build_output_timeline(
    audio_times: np.ndarray,
    step_sec: float,
    max_output_steps: Optional[int] = None,
) -> np.ndarray:
    if len(audio_times) == 0:
        raise RuntimeError("audio_times is empty")
    if step_sec <= 0:
        raise ValueError("output_time_step_sec must be > 0")

    start_t = float(audio_times[0])
    end_t = float(audio_times[-1])

    n_steps = int(np.floor((end_t - start_t) / step_sec)) + 1
    timeline = start_t + np.arange(n_steps, dtype=np.float32) * np.float32(step_sec)
    timeline = timeline[timeline <= (end_t + 1e-6)]

    if len(timeline) == 0:
        timeline = np.array([start_t], dtype=np.float32)

    if max_output_steps is not None and len(timeline) > max_output_steps:
        timeline = timeline[:max_output_steps]

    assert_np_finite("output timeline", timeline)
    return timeline.astype(np.float32)


# ============================================================
# COLUMN HELPERS
# ============================================================
TRANSFORMER_TARGET_COLUMNS = (
    "ear_vec_x",
    "ear_vec_y",
    "ear_vec_z",
    "mid_ear_to_nose_x",
    "mid_ear_to_nose_y",
    "mid_ear_to_nose_z",
    "lip_open_dist_3d",
    "mouth_width_dist_3d",
    "upper_lip_thickness_3d",
    "lower_lip_thickness_3d",
    "brow_eye_left_3d",
    "brow_eye_right_3d",
    "brow_eye_mean_3d",
)

LIP_TARGET_COLUMNS = (
    "lip_open_dist_3d",
    "mouth_width_dist_3d",
    "upper_lip_thickness_3d",
    "lower_lip_thickness_3d",
)

NON_LIP_COLUMNS = (
    "ear_vec_x",
    "ear_vec_y",
    "ear_vec_z",
    "mid_ear_to_nose_x",
    "mid_ear_to_nose_y",
    "mid_ear_to_nose_z",
    "brow_eye_left_3d",
    "brow_eye_right_3d",
    "brow_eye_mean_3d",
)


def build_column_index_map(columns: Tuple[str, ...]) -> Dict[str, int]:
    return {c: i for i, c in enumerate(columns)}


# ============================================================
# PUBLIC INFERENCE FUNCTION
# ============================================================
@torch.no_grad()
def predict_one_wav_without_excel(
    wav_path: str,
    model_dir: str,
    output_time_step_sec: float = 0.04,
    max_output_steps: Optional[int] = None,
    save_csv_path: Optional[str] = None,
    verbose: bool = True,
    lip_mlp_model_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Hybrid inference.

    Parameters
    ----------
    wav_path : str
        Input WAV path.
    model_dir : str
        Transformer model directory (kept same name as old code for compatibility).
    output_time_step_sec : float
        Output timeline step.
    max_output_steps : Optional[int]
        Optional cap on output length.
    save_csv_path : Optional[str]
        Optional output CSV path.
    verbose : bool
        Print logs.
    lip_mlp_model_dir : Optional[str]
        Lip MLP model directory.
        If None, defaults to:
            ./outputs_lip_mlp_local_window
    """
    cleanup_torch_memory()

    if not os.path.isfile(wav_path):
        raise FileNotFoundError(f"WAV not found: {wav_path}")

    if lip_mlp_model_dir is None:
        lip_mlp_model_dir = r"./outputs_lip_mlp_local_window"

    # --------------------------------------------------------
    # Load Transformer
    # --------------------------------------------------------
    trans_model, trans_audio_scaler, trans_y_scaler, trans_cfg = load_transformer_model_and_scalers(model_dir=model_dir, device="cpu")

    # --------------------------------------------------------
    # Load Lip MLP
    # --------------------------------------------------------
    lip_model, lip_audio_scaler, lip_y_scaler, lip_cfg = load_lip_mlp_model_and_scalers(model_dir=lip_mlp_model_dir, device="cpu")

    device="cpu"

    if next(lip_model.parameters()).device != device:
        lip_model = lip_model.to(device)

    if verbose:
        print(f"[INFO] Transformer model dir : {model_dir}")
        print(f"[INFO] Lip MLP model dir     : {lip_mlp_model_dir}")
        print(f"[INFO] Test WAV              : {wav_path}")
        print(f"[INFO] Device                : {device}")

    # --------------------------------------------------------
    # Extract audio twice if configs differ
    # --------------------------------------------------------
    same_audio_config = (
        trans_cfg.sr == lip_cfg.sr and
        trans_cfg.dense_n_fft == lip_cfg.dense_n_fft and
        trans_cfg.dense_win_length == lip_cfg.dense_win_length and
        trans_cfg.dense_hop_length == lip_cfg.dense_hop_length and
        trans_cfg.n_mels == lip_cfg.n_mels and
        trans_cfg.n_mfcc == lip_cfg.n_mfcc and
        trans_cfg.fmin == lip_cfg.fmin and
        trans_cfg.fmax == lip_cfg.fmax and
        trans_cfg.roll_percent == lip_cfg.roll_percent and
        trans_cfg.use_mel == lip_cfg.use_mel and
        trans_cfg.use_mel_delta == lip_cfg.use_mel_delta and
        trans_cfg.use_mel_delta2 == lip_cfg.use_mel_delta2 and
        trans_cfg.use_pitch == lip_cfg.use_pitch and
        trans_cfg.use_pitch_delta == lip_cfg.use_pitch_delta and
        trans_cfg.use_energy == lip_cfg.use_energy and
        trans_cfg.use_energy_delta == lip_cfg.use_energy_delta and
        trans_cfg.use_mfcc == lip_cfg.use_mfcc and
        trans_cfg.use_mfcc_delta == lip_cfg.use_mfcc_delta and
        trans_cfg.use_mfcc_delta2 == lip_cfg.use_mfcc_delta2 and
        trans_cfg.use_zcr == lip_cfg.use_zcr and
        trans_cfg.use_spectral_centroid == lip_cfg.use_spectral_centroid and
        trans_cfg.use_spectral_bandwidth == lip_cfg.use_spectral_bandwidth and
        trans_cfg.use_spectral_rolloff == lip_cfg.use_spectral_rolloff and
        trans_cfg.use_spectral_flatness == lip_cfg.use_spectral_flatness and
        trans_cfg.use_voiced_flag == lip_cfg.use_voiced_flag
    )

    if same_audio_config:
        audio_times, audio_x, feat_names = extract_dense_audio_features(wav_path, trans_cfg)
        trans_audio_times = audio_times.copy()
        trans_audio_x = audio_x.copy()
        lip_audio_times = audio_times.copy()
        lip_audio_x = audio_x.copy()
    else:
        trans_audio_times, trans_audio_x, feat_names = extract_dense_audio_features(wav_path, trans_cfg)
        lip_audio_times, lip_audio_x, _ = extract_dense_audio_features(wav_path, lip_cfg)

    # --------------------------------------------------------
    # Truncate per model
    # --------------------------------------------------------
    if trans_cfg.max_audio_frames is not None and len(trans_audio_x) > trans_cfg.max_audio_frames:
        trans_audio_times = trans_audio_times[:trans_cfg.max_audio_frames]
        trans_audio_x = trans_audio_x[:trans_cfg.max_audio_frames]
        if verbose:
            print(f"[INFO] Transformer audio truncated to max_audio_frames={trans_cfg.max_audio_frames}")

    if lip_cfg.max_audio_frames is not None and len(lip_audio_x) > lip_cfg.max_audio_frames:
        lip_audio_times = lip_audio_times[:lip_cfg.max_audio_frames]
        lip_audio_x = lip_audio_x[:lip_cfg.max_audio_frames]
        if verbose:
            print(f"[INFO] Lip MLP audio truncated to max_audio_frames={lip_cfg.max_audio_frames}")

    assert_np_finite("trans raw audio_x", trans_audio_x)
    assert_np_finite("trans raw audio_times", trans_audio_times)
    assert_np_finite("lip raw audio_x", lip_audio_x)
    assert_np_finite("lip raw audio_times", lip_audio_times)

    if verbose:
        print(f"[INFO] Transformer audio feature dim : {trans_audio_x.shape[1]}")
        print(f"[INFO] Transformer dense steps      : {len(trans_audio_times)}")
        print(f"[INFO] Lip MLP audio feature dim   : {lip_audio_x.shape[1]}")
        print(f"[INFO] Lip MLP dense steps         : {len(lip_audio_times)}")

    # --------------------------------------------------------
    # Scale audio per model
    # --------------------------------------------------------
    trans_audio_x_scaled = trans_audio_scaler.transform(trans_audio_x).astype(np.float32)
    lip_audio_x_scaled = lip_audio_scaler.transform(lip_audio_x).astype(np.float32)

    assert_np_finite("trans_audio_x_scaled", trans_audio_x_scaled)
    assert_np_finite("lip_audio_x_scaled", lip_audio_x_scaled)

    if verbose:
        print(f"[INFO] trans_audio_x_scaled abs max: {float(np.max(np.abs(trans_audio_x_scaled))):.6f}")
        print(f"[INFO] lip_audio_x_scaled abs max  : {float(np.max(np.abs(lip_audio_x_scaled))):.6f}")

    # --------------------------------------------------------
    # Build common output timeline
    # Use overlap between both audio sequences
    # --------------------------------------------------------
    start_t = max(float(trans_audio_times[0]), float(lip_audio_times[0]))
    end_t = min(float(trans_audio_times[-1]), float(lip_audio_times[-1]))

    if end_t < start_t:
        raise RuntimeError("Transformer audio range and Lip MLP audio range do not overlap.")

    common_audio_times = np.array([start_t, end_t], dtype=np.float32)
    output_times = build_output_timeline(
        audio_times=common_audio_times,
        step_sec=output_time_step_sec,
        max_output_steps=max_output_steps,
    )

    if verbose:
        print(f"[INFO] Output steps      : {len(output_times)}")
        print(f"[INFO] Output step sec   : {output_time_step_sec}")
        print(f"[INFO] Output time range : {output_times[0]:.4f}s -> {output_times[-1]:.4f}s")

    # --------------------------------------------------------
    # Prepare indices
    # --------------------------------------------------------
    trans_col2idx = build_column_index_map(tuple(trans_cfg.target_columns))
    lip_col2idx = build_column_index_map(tuple(lip_cfg.target_columns))

    # Check columns
    for col in TRANSFORMER_TARGET_COLUMNS:
        if col not in trans_col2idx:
            raise RuntimeError(f"Transformer target column missing: {col}")

    for col in LIP_TARGET_COLUMNS:
        if col not in lip_col2idx:
            raise RuntimeError(f"Lip MLP target column missing: {col}")

    target_dim = len(trans_cfg.target_columns)
    lip_dim = len(lip_cfg.target_columns)
    T_out = len(output_times)

    preds_scaled_transformer_raw = np.zeros((T_out, target_dim), dtype=np.float32)
    preds_final_original = np.zeros((T_out, target_dim), dtype=np.float32)

    # --------------------------------------------------------
    # Histories
    # Transformer history stays in scaled Transformer space
    # Lip history stays in normalized 0-1 Lip MLP space
    # --------------------------------------------------------
    motion_history_transformer = torch.zeros(
        1, trans_cfg.history_length, target_dim,
        dtype=torch.float32, device=device
    )

    motion_history_lip = torch.zeros(
        1, lip_cfg.history_length, lip_dim,
        dtype=torch.float32, device=device
    )

    # --------------------------------------------------------
    # Step-by-step hybrid inference
    # --------------------------------------------------------
    for t in range(T_out):
        current_t = float(output_times[t])

        # ---------------- Transformer prediction ----------------
        trans_audio_win_np = build_audio_window_single(
            audio_x=trans_audio_x_scaled,
            audio_times=trans_audio_times,
            current_time=current_t,
            window_sec=trans_cfg.audio_window_sec,
            max_audio_window_frames=trans_cfg.max_audio_window_frames,
        )
        trans_audio_win_t = torch.from_numpy(trans_audio_win_np).unsqueeze(0).to(device)

        assert_torch_finite("trans_audio_win_t", trans_audio_win_t)
        assert_torch_finite("motion_history_transformer before model", motion_history_transformer)

        pred_trans_scaled_t = trans_model.forward_infer_single(
            audio_window_x=trans_audio_win_t,
            motion_history=motion_history_transformer,
        )
        assert_torch_finite("pred_trans_scaled_t", pred_trans_scaled_t)

        pred_trans_scaled_np = pred_trans_scaled_t.squeeze(0).detach().cpu().numpy().astype(np.float32)
        preds_scaled_transformer_raw[t] = pred_trans_scaled_np

        pred_trans_original_np = trans_y_scaler.inverse_transform(
            pred_trans_scaled_np.reshape(1, -1)
        ).reshape(-1).astype(np.float32)
        assert_np_finite("pred_trans_original_np", pred_trans_original_np)

        # ---------------- Lip MLP prediction ----------------
        lip_audio_win_np = build_audio_window_single_fixed(
            audio_x=lip_audio_x_scaled,
            audio_times=lip_audio_times,
            current_time=current_t,
            window_sec=lip_cfg.audio_window_sec,
            max_audio_window_frames=lip_cfg.max_audio_window_frames,
        )
        lip_audio_win_t = torch.from_numpy(lip_audio_win_np).unsqueeze(0).to(device)

        assert_torch_finite("lip_audio_win_t", lip_audio_win_t)
        assert_torch_finite("motion_history_lip before model", motion_history_lip)

        pred_lip_norm_t = lip_model(
            audio_window_x=lip_audio_win_t,
            motion_history=motion_history_lip,
        )
        assert_torch_finite("pred_lip_norm_t", pred_lip_norm_t)

        pred_lip_norm_np = pred_lip_norm_t.squeeze(0).detach().cpu().numpy().astype(np.float32)
        pred_lip_norm_np = np.clip(pred_lip_norm_np, 0.0, 1.0)

        pred_lip_original_np = lip_y_scaler.inverse_transform(
            pred_lip_norm_np.reshape(1, -1)
        ).reshape(-1).astype(np.float32)
        assert_np_finite("pred_lip_original_np", pred_lip_original_np)

        # ---------------- Merge final output in original scale ----------------
        pred_final_original_np = pred_trans_original_np.copy()
        for lip_col in LIP_TARGET_COLUMNS:
            pred_final_original_np[trans_col2idx[lip_col]] = pred_lip_original_np[lip_col2idx[lip_col]]

        preds_final_original[t] = pred_final_original_np
        assert_np_finite("pred_final_original_np", pred_final_original_np)

        # ----------------------------------------------------
        # Update Transformer history with MERGED final output,
        # but in Transformer scaled space
        # ----------------------------------------------------
        pred_final_scaled_for_transformer_np = trans_y_scaler.transform(
            pred_final_original_np.reshape(1, -1)
        ).reshape(-1).astype(np.float32)
        assert_np_finite("pred_final_scaled_for_transformer_np", pred_final_scaled_for_transformer_np)

        pred_final_scaled_for_transformer_t = torch.from_numpy(
            pred_final_scaled_for_transformer_np
        ).unsqueeze(0).to(device)

        motion_history_transformer = torch.roll(motion_history_transformer, shifts=-1, dims=1)
        motion_history_transformer[:, -1, :] = pred_trans_scaled_t

        # ----------------------------------------------------
        # Update Lip MLP history with its own normalized output
        # ----------------------------------------------------
        pred_lip_norm_t_clipped = torch.from_numpy(pred_lip_norm_np).unsqueeze(0).to(device)

        motion_history_lip = torch.roll(motion_history_lip, shifts=-1, dims=1)
        motion_history_lip[:, -1, :] = pred_lip_norm_t_clipped

        if verbose and ((t + 1) % 100 == 0 or (t + 1) == T_out):
            print(f"[INFO] Predicted {t + 1}/{T_out}")

    # --------------------------------------------------------
    # Final smoothing in original scale
    # Keep same style as old code: smooth final output then export
    # --------------------------------------------------------
    assert_np_finite("preds_final_original before smoothing", preds_final_original)

    pred_out = ema_smooth(preds_final_original, alpha=trans_cfg.pred_smoothing_alpha).astype(np.float32)
    assert_np_finite("pred_out after smoothing", pred_out)

    df_pred = pd.DataFrame(pred_out, columns=list(trans_cfg.target_columns))
    df_pred.insert(0, trans_cfg.time_column, output_times)

    if save_csv_path is not None:
        df_pred.to_csv(save_csv_path, index=False, encoding="utf-8-sig")
        if verbose:
            print(f"[INFO] Saved prediction CSV: {save_csv_path}")

    del trans_model
    del lip_model
    cleanup_torch_memory()
    return df_pred