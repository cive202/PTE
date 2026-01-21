# Line-by-Line Explanation: audio_quality.py

## Overview
This module analyzes audio quality to determine if it's clear enough for MFA (Montreal Forced Aligner) or if WavLM fallback should be used.

---

## Line-by-Line Breakdown

### Lines 1-7: Imports

```python
from __future__ import annotations
```
- **Purpose**: Enables forward references in type hints
- **Why**: Allows using types before definition

```python
from dataclasses import dataclass
```
- **Purpose**: Import dataclass decorator
- **Why**: Creates structured data classes easily

```python
from typing import Optional, Tuple
```
- **Purpose**: Import type hints
- **Why**: `Optional` = can be None, `Tuple` = tuple type

```python
import numpy as np
```
- **Purpose**: Import NumPy for numerical operations
- **Why**: Needed for audio signal processing and array operations

---

### Lines 9-13: AudioQualityMetrics Data Class

```python
@dataclass(frozen=True)
```
- **Purpose**: Create immutable dataclass
- **Why**: Prevents accidental modification of metrics

```python
class AudioQualityMetrics:
```
- **Purpose**: Structure to hold audio quality measurements
- **Why**: Groups related metrics together

```python
    silence_ratio: float
```
- **Purpose**: Fraction of audio that is silence (0.0 to 1.0)
- **Why**: High silence ratio indicates poor audio quality

```python
    rms_mean: float
```
- **Purpose**: Mean Root Mean Square energy across frames
- **Why**: Measures average audio amplitude/volume

```python
    duration_s: float
```
- **Purpose**: Audio duration in seconds
- **Why**: Provides temporal information

---

### Lines 16-40: Audio Reading Function

```python
def _read_audio_mono(path: str) -> Tuple[np.ndarray, int]:
```
- **Purpose**: Read audio file and convert to mono waveform
- **Parameters**: `path` = audio file path
- **Returns**: (waveform array, sample_rate)

```python
    """
    Reads audio using soundfile if available, otherwise falls back to scipy.
    Returns mono float32 in [-1, 1] (best effort) and sample rate.
    """
```
- **Purpose**: Docstring explaining function behavior
- **Why**: Documents fallback mechanism and output format

```python
    try:
        import soundfile as sf  # type: ignore
        
        y, sr = sf.read(path, always_2d=False)
        y = np.asarray(y)
```
- **Purpose**: Try to use soundfile library (preferred)
- **Why**: soundfile is faster and handles more formats
- **`always_2d=False`**: Returns 1D array for mono, 2D for stereo

```python
    except Exception:
```
- **Purpose**: Catch any error (import or read failure)
- **Why**: Provides fallback to scipy

```python
        # Fallback: scipy wav reader
        from scipy.io import wavfile  # type: ignore
        
        sr, y = wavfile.read(path)
        y = np.asarray(y)
```
- **Purpose**: Use scipy as backup audio reader
- **Why**: scipy is more commonly installed
- **Note**: scipy returns (sample_rate, data) in different order

```python
        # convert integer PCM to float
        if np.issubdtype(y.dtype, np.integer):
            maxv = np.iinfo(y.dtype).max
            y = y.astype(np.float32) / float(maxv)
```
- **Purpose**: Convert integer PCM samples to float [-1, 1]
- **Why**: Standardizes audio format for processing
- **Process**: Divides by max value to normalize

```python
    if y.ndim == 2:
        y = y.mean(axis=1)
```
- **Purpose**: Convert stereo to mono by averaging channels
- **Why**: Simplifies processing (mono is sufficient)

```python
    y = y.astype(np.float32)
```
- **Purpose**: Ensure float32 type
- **Why**: Consistent data type for calculations

```python
    return y, int(sr)
```
- **Purpose**: Return waveform and sample rate
- **Why**: Provides audio data for analysis

---

### Lines 43-84: Audio Quality Metrics Computation

```python
def compute_audio_quality_metrics(
    wav_path: str,
    frame_ms: float = 30.0,
    hop_ms: float = 10.0,
    silence_rms_threshold: float = 0.01,
) -> AudioQualityMetrics:
```
- **Purpose**: Compute audio quality metrics
- **Parameters**:
  - `wav_path`: Audio file path
  - `frame_ms`: Frame length in milliseconds (default 30ms)
  - `hop_ms`: Hop size in milliseconds (default 10ms)
  - `silence_rms_threshold`: RMS threshold for silence detection (default 0.01)
- **Returns**: AudioQualityMetrics object

```python
    """
    Basic, dependency-light audio clarity metrics.
    
    - **silence_ratio**: fraction of frames whose RMS < threshold
    - **rms_mean**: mean frame RMS
    - **duration_s**: audio duration in seconds
    """
```
- **Purpose**: Docstring explaining metrics
- **Why**: Documents what each metric means

```python
    y, sr = _read_audio_mono(wav_path)
```
- **Purpose**: Load audio file
- **Why**: Gets waveform and sample rate for analysis

```python
    if y.size == 0 or sr <= 0:
        return AudioQualityMetrics(silence_ratio=1.0, rms_mean=0.0, duration_s=0.0)
```
- **Purpose**: Handle empty or invalid audio
- **Why**: Prevents division by zero and errors
- **Returns**: Worst-case metrics (all silence)

```python
    frame_len = max(1, int(sr * (frame_ms / 1000.0)))
```
- **Purpose**: Calculate frame length in samples
- **Formula**: sample_rate × (frame_ms / 1000)
- **`max(1, ...)`**: Ensures at least 1 sample

```python
    hop_len = max(1, int(sr * (hop_ms / 1000.0)))
```
- **Purpose**: Calculate hop size in samples
- **Why**: Determines frame overlap (30ms frames, 10ms hop = 20ms overlap)

```python
    n_frames = 1 + max(0, (len(y) - frame_len) // hop_len)
```
- **Purpose**: Calculate number of frames
- **Formula**: 1 + floor((audio_length - frame_length) / hop_length)
- **Why**: Accounts for partial frames

```python
    if n_frames <= 0:
        rms = float(np.sqrt(np.mean(y**2))) if y.size else 0.0
        silence_ratio = 1.0 if rms < silence_rms_threshold else 0.0
        return AudioQualityMetrics(silence_ratio=silence_ratio, rms_mean=rms, duration_s=len(y) / sr)
```
- **Purpose**: Handle very short audio (shorter than one frame)
- **Why**: Edge case handling
- **RMS calculation**: sqrt(mean(samples²)) = root mean square

```python
    rms_vals = []
```
- **Purpose**: Initialize list for RMS values per frame
- **Why**: Will store energy for each frame

```python
    for i in range(n_frames):
        start = i * hop_len
        frame = y[start : start + frame_len]
```
- **Purpose**: Extract each frame with hop
- **Why**: Analyzes audio in overlapping windows

```python
        if frame.size == 0:
            continue
```
- **Purpose**: Skip empty frames
- **Why**: Prevents errors in RMS calculation

```python
        rms_vals.append(float(np.sqrt(np.mean(frame**2))))
```
- **Purpose**: Calculate RMS for this frame and add to list
- **Formula**: sqrt(mean(frame²))
- **Why**: Measures energy/amplitude of frame

```python
    if not rms_vals:
        return AudioQualityMetrics(silence_ratio=1.0, rms_mean=0.0, duration_s=len(y) / sr)
```
- **Purpose**: Handle case where no valid frames found
- **Why**: Safety check

```python
    rms_arr = np.asarray(rms_vals, dtype=np.float32)
```
- **Purpose**: Convert list to NumPy array
- **Why**: Enables vectorized operations

```python
    silence_ratio = float(np.mean(rms_arr < silence_rms_threshold))
```
- **Purpose**: Calculate fraction of frames below silence threshold
- **Process**: `rms_arr < threshold` creates boolean array, `mean()` gives ratio
- **Why**: Measures how much of audio is silence

```python
    rms_mean = float(np.mean(rms_arr))
```
- **Purpose**: Calculate average RMS across all frames
- **Why**: Measures overall audio energy

```python
    duration_s = float(len(y) / sr)
```
- **Purpose**: Calculate audio duration
- **Formula**: samples / sample_rate = seconds
- **Why**: Provides temporal information

```python
    return AudioQualityMetrics(silence_ratio=silence_ratio, rms_mean=rms_mean, duration_s=duration_s)
```
- **Purpose**: Return computed metrics
- **Why**: Provides audio quality assessment

---

### Lines 87-106: Audio Clarity Decision Function

```python
def is_audio_clear(
    wav_path: str,
    *,
    asr_confidence: Optional[float] = None,
    silence_ratio_threshold: float = 0.35,
    asr_confidence_threshold: float = 0.75,
    silence_rms_threshold: float = 0.01,
) -> Tuple[bool, AudioQualityMetrics]:
```
- **Purpose**: Determine if audio is clear enough for MFA
- **Parameters**:
  - `wav_path`: Audio file path
  - `asr_confidence`: ASR confidence score (optional)
  - `silence_ratio_threshold`: Max silence ratio for clear audio (default 0.35)
  - `asr_confidence_threshold`: Min ASR confidence for clear audio (default 0.75)
  - `silence_rms_threshold`: RMS threshold for silence (default 0.01)
- **Returns**: (is_clear boolean, metrics object)

```python
    """
    Returns (audio_clear, metrics).
    
    The plan's gate uses ASR confidence + silence ratio. If you don't have
    ASR confidence yet, pass None and the gate will fall back to silence ratio only.
    """
```
- **Purpose**: Docstring explaining decision logic
- **Why**: Documents the clarity gate mechanism

```python
    metrics = compute_audio_quality_metrics(wav_path, silence_rms_threshold=silence_rms_threshold)
```
- **Purpose**: Compute audio quality metrics
- **Why**: Gets silence ratio and other measurements

```python
    if asr_confidence is None:
        return metrics.silence_ratio < silence_ratio_threshold, metrics
```
- **Purpose**: If no ASR confidence, use only silence ratio
- **Decision**: Clear if silence ratio < threshold (35%)
- **Why**: Fallback when ASR confidence unavailable

```python
    audio_clear = (asr_confidence > asr_confidence_threshold) and (metrics.silence_ratio < silence_ratio_threshold)
```
- **Purpose**: Combined decision: clear if BOTH conditions met
- **Conditions**:
  1. ASR confidence > 0.75
  2. Silence ratio < 0.35
- **Why**: Requires both good ASR performance and low silence

```python
    return audio_clear, metrics
```
- **Purpose**: Return decision and metrics
- **Why**: Provides clarity assessment for routing

---

## Summary

This module implements the **audio clarity gate**:
1. **Reads** audio files (with fallback support)
2. **Computes** silence ratio and RMS energy
3. **Decides** if audio is clear based on ASR confidence + silence ratio
4. **Routes** to MFA (clear) or WavLM (noisy) for pronunciation assessment

The key insight: **Audio clarity determines which pronunciation method to use, not content detection.**
