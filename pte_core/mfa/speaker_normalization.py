"""Speaker normalization for accent-tolerant scoring."""
from __future__ import annotations

import statistics
from typing import Any, Dict, List

from .accent_config import SPEAKER_BASELINE_DURATION


def _normalize_phone_label(label: str) -> str:
    """Normalize phone label (remove stress markers, convert to uppercase)."""
    return label.upper().rstrip("012")


def _is_vowel(phone_label: str) -> bool:
    """Check if phone is a vowel."""
    vowels = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", 
              "IH", "IY", "OW", "OY", "UH", "UW"}
    normalized = _normalize_phone_label(phone_label)
    return normalized in vowels


def _is_consonant(phone_label: str) -> bool:
    """Check if phone is a consonant."""
    consonants = {"B", "CH", "D", "DH", "F", "G", "HH", "JH", "K", "L",
                  "M", "N", "NG", "P", "R", "S", "SH", "T", "TH", "V",
                  "W", "Y", "Z", "ZH"}
    normalized = _normalize_phone_label(phone_label)
    return normalized in consonants


def analyze_speaker_baseline(
    phones: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    duration: float = SPEAKER_BASELINE_DURATION,
) -> Dict[str, float]:
    """Analyze first N seconds of speech to establish speaker baseline.
    
    This learns the speaker's natural speech patterns (rate, timing, etc.)
    so scoring can be relative to the speaker, not a native model.
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        words: List of word alignments: {word, start, end, ...}
        duration: Duration to analyze (default: 3.0 seconds)
        
    Returns:
        Dict with baseline metrics:
            - speech_rate: phones per second
            - median_vowel_duration: median vowel duration
            - median_consonant_duration: median consonant duration
            - avg_pause_duration: average pause between phones
            - vowel_ratio: vowel duration / total duration
            - phone_count: number of phones analyzed
    """
    # Filter phones within baseline duration
    baseline_phones = [
        p for p in phones
        if p.get("start", 0.0) < duration
        and p.get("label", "").strip().upper() not in ("SP", "SIL", "")
    ]
    
    if not baseline_phones:
        # Return default baseline if no phones found
        return {
            "speech_rate": 10.0,  # Default reasonable rate
            "median_vowel_duration": 0.10,
            "median_consonant_duration": 0.06,
            "avg_pause_duration": 0.1,
            "vowel_ratio": 0.4,
            "phone_count": 0,
        }
    
    # Calculate speech rate
    if baseline_phones:
        first_start = baseline_phones[0].get("start", 0.0)
        last_end = baseline_phones[-1].get("end", 0.0)
        actual_duration = min(last_end - first_start, duration)
        speech_rate = len(baseline_phones) / actual_duration if actual_duration > 0 else 10.0
    else:
        speech_rate = 10.0
    
    # Separate vowels and consonants
    vowel_durations: List[float] = []
    consonant_durations: List[float] = []
    total_vowel_duration = 0.0
    total_duration = 0.0
    
    for phone in baseline_phones:
        label = phone.get("label", "")
        phone_duration = phone.get("duration", 0.0)
        total_duration += phone_duration
        
        if _is_vowel(label):
            vowel_durations.append(phone_duration)
            total_vowel_duration += phone_duration
        elif _is_consonant(label):
            consonant_durations.append(phone_duration)
    
    # Calculate medians
    median_vowel = statistics.median(vowel_durations) if vowel_durations else 0.10
    median_consonant = statistics.median(consonant_durations) if consonant_durations else 0.06
    
    # Calculate average pause duration
    pauses: List[float] = []
    sorted_phones = sorted(baseline_phones, key=lambda p: p.get("start", 0.0))
    for i in range(len(sorted_phones) - 1):
        current_end = sorted_phones[i].get("end", 0.0)
        next_start = sorted_phones[i + 1].get("start", 0.0)
        gap = next_start - current_end
        if gap > 0:
            pauses.append(gap)
    
    avg_pause = statistics.mean(pauses) if pauses else 0.1
    
    # Calculate vowel ratio
    vowel_ratio = total_vowel_duration / total_duration if total_duration > 0 else 0.4
    
    return {
        "speech_rate": speech_rate,
        "median_vowel_duration": median_vowel,
        "median_consonant_duration": median_consonant,
        "avg_pause_duration": avg_pause,
        "vowel_ratio": vowel_ratio,
        "phone_count": len(baseline_phones),
    }


# Reference native medians (approximate generic English values)
NATIVE_VOWEL_MEDIAN = 0.12
NATIVE_CONSONANT_MEDIAN = 0.06

def normalize_timing(
    phone_duration: float,
    phone_label: str,
    baseline: Dict[str, float],
    native_expected: float,
    native_std: float,
) -> float:
    """Convert absolute phone duration to relative z-score using speaker scaling.
    
    Instead of comparing raw duration vs native expected, we:
    1. Calculate speaker's scaling factor (e.g., speaker is 1.2x slower than native).
    2. Scale the specific phone's expected duration by this factor.
    3. Compute Z-score against this scaled expectation.
    
    This preserves the relative timing differences between phonemes (e.g., 'AA' > 'IH')
    while adapting to the speaker's overall speech rate.
    
    Args:
        phone_duration: Observed phone duration
        phone_label: The phone label (e.g., "AA", "T")
        baseline: Speaker baseline dict from analyze_speaker_baseline()
        native_expected: The native expected duration for this specific phoneme
        native_std: The native standard deviation for this specific phoneme
        
    Returns:
        Z-score relative to speaker-scaled expectation
    """
    # Determine phone type for scaling factor selection
    if _is_vowel(phone_label):
        speaker_median = baseline.get("median_vowel_duration", 0.10)
        native_median = NATIVE_VOWEL_MEDIAN
    elif _is_consonant(phone_label):
        speaker_median = baseline.get("median_consonant_duration", 0.06)
        native_median = NATIVE_CONSONANT_MEDIAN
    else:
        # Fallback for silence or non-speech phones - no scaling applied usually
        # or treat as consonant-like scaling
        return (phone_duration - native_expected) / native_std if native_std > 0 else 0.0
    
    # Calculate scaling factor (speaker speed vs native speed)
    # If speaker_median is 0.12 and native is 0.10, factor is 1.2 (speaker is slower)
    scaling_factor = speaker_median / native_median if native_median > 0 else 1.0
    
    # Scale both expected mean and standard deviation
    expected = native_expected * scaling_factor
    std = native_std * scaling_factor
    
    if std <= 0:
        return 0.0
    
    z_score = (phone_duration - expected) / std
    return z_score


def is_intelligible(
    phones: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    baseline: Dict[str, float],
) -> bool:
    """Check if speech is intelligible based on heuristics.
    
    Intelligibility checks:
    - Speech rate within reasonable range
    - Vowel quality maintained (even if accent-shifted)
    - No excessive pauses
    - Consistent phone patterns
    
    Args:
        phones: List of phone alignments
        words: List of word alignments
        baseline: Speaker baseline dict
        
    Returns:
        True if speech appears intelligible, False otherwise
    """
    from .accent_config import (
        MAX_AVERAGE_PAUSE,
        MAX_SPEECH_RATE,
        MIN_SPEECH_RATE,
    )
    
    # Check speech rate
    speech_rate = baseline.get("speech_rate", 10.0)
    if speech_rate < MIN_SPEECH_RATE or speech_rate > MAX_SPEECH_RATE:
        return False
    
    # Check pause patterns
    avg_pause = baseline.get("avg_pause_duration", 0.1)
    if avg_pause > MAX_AVERAGE_PAUSE:
        return False
    
    # Check if we have reasonable phone coverage
    phone_count = baseline.get("phone_count", 0)
    if phone_count < 10:  # Too few phones indicates problems
        return False
    
    # Check vowel ratio (should be reasonable)
    vowel_ratio = baseline.get("vowel_ratio", 0.4)
    if vowel_ratio < 0.2 or vowel_ratio > 0.7:  # Extreme ratios indicate problems
        return False
    
    # If all checks pass, speech is likely intelligible
    return True
