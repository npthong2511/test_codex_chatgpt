from __future__ import annotations

import hashlib
import unicodedata
import re

import numpy as np


HASH_DIM = 4096


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stable_feature_index(feature: str, dimension: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "little", signed=False)
    return value % dimension, 1.0 if ((value >> 63) & 1) == 0 else -1.0


def hashing_vector(text: str, dimension: int = HASH_DIM) -> np.ndarray:
    norm = normalize_text(text)
    vec = np.zeros(dimension, dtype=np.float32)
    words = norm.split()
    features: list[tuple[str, float]] = []
    features.extend((f"w:{w}", 1.0) for w in words)
    features.extend((f"b:{words[i]}_{words[i+1]}", 1.35) for i in range(len(words) - 1))
    compact = norm.replace(" ", "_")
    for n in (3, 4, 5):
        features.extend((f"c{n}:{compact[i:i+n]}", 0.20) for i in range(max(0, len(compact) - n + 1)))
    for feature, weight in features:
        idx, sign = stable_feature_index(feature, dimension)
        vec[idx] += np.float32(sign * weight)
    length = float(np.linalg.norm(vec))
    if length > 0:
        vec /= length
    return vec
