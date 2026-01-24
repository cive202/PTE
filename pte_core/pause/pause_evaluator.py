"""Pause evaluation logic for punctuation marks."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .rules import (
    BASE_PAUSE_THRESHOLDS,
    MISSED_PAUSE_PENALTIES,
    MAX_PAUSE_DURATION,
    FUNCTION_WORDS,
    SHORT_PAUSE_SOFT_FLOOR,
)


def evaluate_pause(
    punct: str,
    pause_duration: Optional[float],
    prev_end: Optional[float],
    next_start: Optional[float],
    speech_rate_scale: float = 1.0,
    prev_word: Optional[str] = None,
    is_after_repeated: bool = False
) -> Dict[str, Any]:
    """Evaluate pause at a punctuation mark with PTE-style penalty scoring.
    
    Returns a dict with pause status, penalty, and details.
    
    Args:
        punct: The punctuation mark ("," or ".")
        pause_duration: The measured pause duration in seconds (or None)
        prev_end: End timestamp of previous word
        next_start: Start timestamp of next word
        speech_rate_scale: Scaling factor for adaptive thresholds (default: 1.0)
        prev_word: Previous word before punctuation (for function word detection)
        is_after_repeated: Whether the pause follows a repeated word (PTE-specific penalty)
        
    Returns:
        Dictionary with pause evaluation results:
        - word: The punctuation mark
        - status: "correct_pause", "short_pause", "long_pause", or "missed_pause"
        - penalty: Numeric penalty (0.0-1.0) for fluency scoring
        - pause_duration: Actual pause duration (or None)
        - expected_range: Tuple of (min, max) expected pause duration (scaled)
        - start: Previous word end timestamp
        - end: Next word start timestamp
    """
    # Get base thresholds and scale by speech rate
    base_min, base_max = BASE_PAUSE_THRESHOLDS.get(punct, (0.3, 0.5))
    min_pause = base_min * speech_rate_scale
    max_pause = base_max * speech_rate_scale
    
    result = {
        "word": punct,
        "expected_range": (min_pause, max_pause),
        "start": prev_end,
        "end": next_start,
    }
    
    # Calculate penalty based on PTE scoring logic
    if pause_duration is None:
        # Missed pause: dynamic penalty for comma (scaled by speech rate), fixed for period
        result["status"] = "missed_pause"
        result["pause_duration"] = None
        
        if punct == ",":
            # Comma missed pause: dynamic based on speech rate (lower for fast speakers)
            base_penalty = MISSED_PAUSE_PENALTIES.get(",", 0.05)
            result["penalty"] = base_penalty * speech_rate_scale
        else:
            result["penalty"] = MISSED_PAUSE_PENALTIES.get(punct, 0.3)
        
    elif pause_duration < min_pause:
        # Short pause: soft floor to ignore small deviations
        result["status"] = "short_pause"
        result["pause_duration"] = pause_duration
        
        # Calculate ratio of deviation
        ratio = (min_pause - pause_duration) / min_pause
        
        # Soft floor: ignore deviations < 30% of min_pause
        if ratio <= SHORT_PAUSE_SOFT_FLOOR:
            short_penalty = 0.0  # Ignore small deviations
        else:
            # Scale remaining deviation to 0-0.3 range
            adjusted_ratio = (ratio - SHORT_PAUSE_SOFT_FLOOR) / (1 - SHORT_PAUSE_SOFT_FLOOR)
            short_penalty = adjusted_ratio * 0.3
        
        # Reduce penalty for commas (less important)
        if punct == ",":
            short_penalty *= 0.5
        
        result["penalty"] = min(short_penalty, 0.3)
        
    elif pause_duration > max_pause:
        # Long pause: strongly penalized, capped at 1.0
        result["status"] = "long_pause"
        result["pause_duration"] = pause_duration
        
        # Calculate proportional penalty
        excess = pause_duration - max_pause
        long_penalty = min(excess / max_pause, 1.0)
        
        # Cap at 1.0 for excessive pauses (>1.5s)
        if pause_duration > MAX_PAUSE_DURATION:
            result["penalty"] = 1.0
        else:
            # Scale penalty: 0.5-1.0 based on excess
            result["penalty"] = 0.5 + (long_penalty * 0.5)
        
    else:
        # Correct pause: no penalty
        result["status"] = "correct_pause"
        result["pause_duration"] = pause_duration
        result["penalty"] = 0.0
    
    # Apply function word penalty reduction
    if prev_word and prev_word.lower() in FUNCTION_WORDS:
        result["penalty"] *= 0.6  # Reduce penalty by 40% for function words
    
    # Amplify penalty for pauses after repeated words (PTE-specific)
    if is_after_repeated:
        result["penalty"] *= 1.5
        result["penalty"] = min(result["penalty"], 1.0)  # Cap at 1.0
    
    return result
