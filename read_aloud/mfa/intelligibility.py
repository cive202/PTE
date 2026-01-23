"""Intelligibility assessment for accent-tolerant scoring."""
from __future__ import annotations

from typing import Any, Dict, List

from .accent_config import (
    MAX_AVERAGE_PAUSE,
    MAX_SPEECH_RATE,
    MIN_SPEECH_RATE,
    VOWEL_QUALITY_THRESHOLD,
)
from .speaker_normalization import analyze_speaker_baseline
from .timing_metrics import calculate_phone_rate, calculate_vowel_ratio


def assess_intelligibility(
    phones: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    baseline: Dict[str, float],
) -> Dict[str, Any]:
    """Assess overall intelligibility of speech.
    
    Checks multiple intelligibility factors:
    - Speech rate stability
    - Vowel quality (even if accent-shifted)
    - Consonant clarity
    - Pause patterns
    - Overall consistency
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        words: List of word alignments: {word, start, end, ...}
        baseline: Speaker baseline dict from analyze_speaker_baseline()
        
    Returns:
        Dict with:
            - is_intelligible: bool
            - confidence: float (0.0-1.0)
            - factors: Dict with individual factor scores
    """
    factors: Dict[str, Any] = {}
    
    # Factor 1: Speech rate stability
    speech_rate = baseline.get("speech_rate", 10.0)
    if MIN_SPEECH_RATE <= speech_rate <= MAX_SPEECH_RATE:
        rate_score = 1.0
    elif speech_rate < MIN_SPEECH_RATE:
        # Too slow - penalize but don't fail
        rate_score = max(0.3, (speech_rate / MIN_SPEECH_RATE))
    else:
        # Too fast - penalize but don't fail
        rate_score = max(0.3, (MAX_SPEECH_RATE / speech_rate))
    factors["speech_rate"] = rate_score
    
    # Factor 2: Pause patterns
    avg_pause = baseline.get("avg_pause_duration", 0.1)
    if avg_pause <= MAX_AVERAGE_PAUSE:
        pause_score = 1.0
    else:
        # Excessive pauses - penalize
        pause_score = max(0.2, MAX_AVERAGE_PAUSE / avg_pause)
    factors["pause_patterns"] = pause_score
    
    # Factor 3: Vowel quality (check if vowels are present and reasonable)
    vowel_ratio = baseline.get("vowel_ratio", 0.4)
    if 0.2 <= vowel_ratio <= 0.7:
        vowel_score = 1.0
    else:
        # Extreme ratios - penalize
        if vowel_ratio < 0.2:
            vowel_score = vowel_ratio / 0.2
        else:
            vowel_score = (1.0 - vowel_ratio) / 0.3
        vowel_score = max(0.3, vowel_score)
    factors["vowel_quality"] = vowel_score
    
    # Factor 4: Phone coverage (enough phones detected)
    phone_count = baseline.get("phone_count", 0)
    if phone_count >= 20:
        coverage_score = 1.0
    elif phone_count >= 10:
        coverage_score = phone_count / 20.0
    else:
        coverage_score = max(0.2, phone_count / 10.0)
    factors["phone_coverage"] = coverage_score
    
    # Factor 5: Consistency (variance in phone durations)
    if phones:
        durations = [p.get("duration", 0.0) for p in phones if p.get("label", "").strip().upper() not in ("SP", "SIL", "")]
        if durations:
            import statistics
            if len(durations) > 1:
                duration_std = statistics.stdev(durations)
                duration_mean = statistics.mean(durations)
                cv = duration_std / duration_mean if duration_mean > 0 else 1.0
                # Low coefficient of variation = more consistent
                consistency_score = max(0.3, 1.0 - min(1.0, cv))
            else:
                consistency_score = 1.0
        else:
            consistency_score = 0.5
    else:
        consistency_score = 0.0
    factors["consistency"] = consistency_score
    
    # Calculate overall intelligibility score
    # Weight factors (speech rate and consistency are most important)
    weights = {
        "speech_rate": 0.25,
        "pause_patterns": 0.20,
        "vowel_quality": 0.20,
        "phone_coverage": 0.15,
        "consistency": 0.20,
    }
    
    confidence = sum(weights.get(factor, 0.0) * factors.get(factor, 0.0) 
                    for factor in weights)
    
    # Intelligible if confidence >= 0.6
    is_intelligible = confidence >= 0.6
    
    return {
        "is_intelligible": is_intelligible,
        "confidence": confidence,
        "factors": factors,
    }


def calculate_intelligibility_score(
    phones: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
) -> float:
    """Calculate composite intelligibility score (0.0-1.0).
    
    Simplified version that doesn't require baseline.
    Used for quick intelligibility checks.
    
    Args:
        phones: List of phone alignments
        words: List of word alignments
        
    Returns:
        Intelligibility score (0.0-1.0)
    """
    if not phones or not words:
        return 0.0
    
    # Quick checks
    phone_rate = calculate_phone_rate(phones)
    vowel_ratio = calculate_vowel_ratio(phones)
    
    # Simple scoring
    score = 1.0
    
    # Check speech rate
    if phone_rate < MIN_SPEECH_RATE or phone_rate > MAX_SPEECH_RATE:
        score *= 0.7
    
    # Check vowel ratio
    if vowel_ratio < 0.2 or vowel_ratio > 0.7:
        score *= 0.8
    
    # Check phone count
    non_silence_phones = [p for p in phones if p.get("label", "").strip().upper() not in ("SP", "SIL", "")]
    if len(non_silence_phones) < 10:
        score *= 0.6
    
    return score
