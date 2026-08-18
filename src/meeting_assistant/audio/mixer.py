"""PCM conversion without pretending independent sources are diarized."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from scipy.signal import resample_poly

TARGET_RATE = 16000


def normalize_for_whisper(samples: NDArray[np.float32], source_rate: int) -> NDArray[np.float32]:
    """Downmix, resample, remove DC, and safely limit float PCM."""
    if samples.ndim == 2:
        mono = samples.mean(axis=1, dtype=np.float32)
    else:
        mono = samples.astype(np.float32, copy=False)
    if mono.size == 0:
        return mono
    mono = mono - np.mean(mono, dtype=np.float32)
    if source_rate != TARGET_RATE:
        divisor = math.gcd(source_rate, TARGET_RATE)
        mono = resample_poly(mono, TARGET_RATE // divisor, source_rate // divisor).astype(
            np.float32
        )
    peak = float(np.max(np.abs(mono)))
    if peak > 1.0:
        mono = mono / peak
    return np.clip(mono, -1.0, 1.0).astype(np.float32)


def pcm16_bytes(samples: NDArray[np.float32]) -> bytes:
    return bytes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
