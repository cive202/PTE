from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class AudioQualityMetrics:
    silence_ratio: float
    rms_mean: float
    duration_s: float


def _read_audio_mono(path: str) -> Tuple[np.ndarray, int]:
    """
    Reads audio using soundfile if available, otherwise falls back to scipy.
    Returns mono float32 in [-1, 1] (best effort) and sample rate.
    """
    try:
        import soundfile as sf  # type: ignore

        y, sr = sf.read(path, always_2d=False)
        y = np.asarray(y)
    except Exception:
        # Fallback: scipy wav reader
        from scipy.io import wavfile  # type: ignore

        sr, y = wavfile.read(path)
        y = np.asarray(y)
        # convert integer PCM to float
        if np.issubdtype(y.dtype, np.integer):
            maxv = np.iinfo(y.dtype).max
            y = y.astype(np.float32) / float(maxv)

    if y.ndim == 2:
        y = y.mean(axis=1)
    y = y.astype(np.float32)
    return y, int(sr)


def compute_audio_quality_metrics(
    wav_path: str,
    frame_ms: float = 30.0,
    hop_ms: float = 10.0,
    silence_rms_threshold: float = 0.01,
) -> AudioQualityMetrics:
    """
    Basic, dependency-light audio clarity metrics.

    - **silence_ratio**: fraction of frames whose RMS < threshold
    - **rms_mean**: mean frame RMS
    - **duration_s**: audio duration in seconds
    """
    y, sr = _read_audio_mono(wav_path)
    if y.size == 0 or sr <= 0:
        return AudioQualityMetrics(silence_ratio=1.0, rms_mean=0.0, duration_s=0.0)

    frame_len = max(1, int(sr * (frame_ms / 1000.0)))
    hop_len = max(1, int(sr * (hop_ms / 1000.0)))
    n_frames = 1 + max(0, (len(y) - frame_len) // hop_len)

    if n_frames <= 0:
        rms = float(np.sqrt(np.mean(y**2))) if y.size else 0.0
        silence_ratio = 1.0 if rms < silence_rms_threshold else 0.0
        return AudioQualityMetrics(silence_ratio=silence_ratio, rms_mean=rms, duration_s=len(y) / sr)

    rms_vals = []
    for i in range(n_frames):
        start = i * hop_len
        frame = y[start : start + frame_len]
        if frame.size == 0:
            continue
        rms_vals.append(float(np.sqrt(np.mean(frame**2))))

    if not rms_vals:
        return AudioQualityMetrics(silence_ratio=1.0, rms_mean=0.0, duration_s=len(y) / sr)

    rms_arr = np.asarray(rms_vals, dtype=np.float32)
    silence_ratio = float(np.mean(rms_arr < silence_rms_threshold))
    rms_mean = float(np.mean(rms_arr))
    duration_s = float(len(y) / sr)
    return AudioQualityMetrics(silence_ratio=silence_ratio, rms_mean=rms_mean, duration_s=duration_s)


def is_audio_clear(
    wav_path: str,
    *,
    asr_confidence: Optional[float] = None,
    silence_ratio_threshold: float = 0.35,
    asr_confidence_threshold: float = 0.75,
    silence_rms_threshold: float = 0.01,
) -> Tuple[bool, AudioQualityMetrics]:
    """
    Returns (audio_clear, metrics).

    The plan's gate uses ASR confidence + silence ratio. If you don't have
    ASR confidence yet, pass None and the gate will fall back to silence ratio only.
    """
    metrics = compute_audio_quality_metrics(wav_path, silence_rms_threshold=silence_rms_threshold)
    if asr_confidence is None:
        return metrics.silence_ratio < silence_ratio_threshold, metrics

    audio_clear = (asr_confidence > asr_confidence_threshold) and (metrics.silence_ratio < silence_ratio_threshold)
    return audio_clear, metrics

