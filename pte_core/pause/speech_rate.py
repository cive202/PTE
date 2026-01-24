"""Speech rate calculation for adaptive pause thresholds."""
from __future__ import annotations

from typing import Any, Dict, List

from .rules import BASE_INTER_WORD_GAP


def calculate_speech_rate_scale(asr_words: List[Dict[str, Any]]) -> float:
    """Calculate speech rate scaling factor based on average inter-word gap.
    
    Args:
        asr_words: List of ASR word entries with timestamps
        
    Returns:
        Scaling factor (1.0 = normal rate, >1.0 = slower, <1.0 = faster)
    """
    if len(asr_words) < 2:
        return 1.0
    
    gaps = []
    for i in range(len(asr_words) - 1):
        curr_end = asr_words[i].get("end") or asr_words[i].get("value", {}).get("end")
        next_start = asr_words[i + 1].get("start") or asr_words[i + 1].get("value", {}).get("start")
        
        if curr_end is not None and next_start is not None:
            gap = next_start - curr_end
            if gap > 0:  # Only count positive gaps
                gaps.append(gap)
    
    if not gaps:
        return 1.0
    
    avg_gap = sum(gaps) / len(gaps)
    
    # Scale factor: normalize to base inter-word gap
    scale = avg_gap / BASE_INTER_WORD_GAP
    
    # Clamp to reasonable range (0.5x to 2.0x)
    return max(0.5, min(2.0, scale))
