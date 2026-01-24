"""Word and phone duration metrics for timing and rhythm analysis."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def calculate_word_duration(word_alignments: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate word duration statistics.
    
    Args:
        word_alignments: List of word alignments: {word, start, end, ...}
        
    Returns:
        Dict with:
            - total_duration: Total duration of all words
            - avg_word_duration: Average word duration
            - word_count: Number of words
    """
    if not word_alignments:
        return {
            "total_duration": 0.0,
            "avg_word_duration": 0.0,
            "word_count": 0,
        }
    
    durations = []
    for word_align in word_alignments:
        start = word_align.get("start")
        end = word_align.get("end")
        if start is not None and end is not None:
            durations.append(end - start)
    
    if not durations:
        return {
            "total_duration": 0.0,
            "avg_word_duration": 0.0,
            "word_count": 0,
        }
    
    return {
        "total_duration": sum(durations),
        "avg_word_duration": sum(durations) / len(durations),
        "word_count": len(durations),
    }


def calculate_phone_rate(phones: List[Dict[str, Any]]) -> float:
    """Calculate phone rate (phones per second) - fluency indicator.
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        
    Returns:
        Phone rate (phones per second), or 0.0 if no phones
    """
    if not phones:
        return 0.0
    
    # Filter out silence
    non_silence_phones = [
        p for p in phones
        if p.get("label", "").strip().upper() not in ("SP", "SIL", "")
    ]
    
    if not non_silence_phones:
        return 0.0
    
    # Calculate total duration
    first_phone = non_silence_phones[0]
    last_phone = non_silence_phones[-1]
    total_duration = last_phone.get("end", 0.0) - first_phone.get("start", 0.0)
    
    if total_duration <= 0:
        return 0.0
    
    return len(non_silence_phones) / total_duration


def calculate_vowel_ratio(phones: List[Dict[str, Any]]) -> float:
    """Calculate vowel-to-consonant ratio - accent detection.
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        
    Returns:
        Ratio of vowel duration to total phone duration (0.0 to 1.0)
    """
    if not phones:
        return 0.0
    
    vowel_duration = 0.0
    total_duration = 0.0
    
    vowels = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", 
              "IH", "IY", "OW", "OY", "UH", "UW"}
    
    for phone in phones:
        label = phone.get("label", "").strip().upper()
        if label in ("SP", "SIL", ""):
            continue
        
        # Remove stress markers
        normalized = label.rstrip("012")
        duration = phone.get("duration", 0.0)
        total_duration += duration
        
        if normalized in vowels:
            vowel_duration += duration
    
    if total_duration == 0:
        return 0.0
    
    return vowel_duration / total_duration


def detect_hesitation(
    phones: List[Dict[str, Any]],
    threshold: float = 0.2,
) -> List[Dict[str, Any]]:
    """Detect hesitation based on silence between phones.
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        threshold: Minimum silence duration to count as hesitation (seconds)
        
    Returns:
        List of hesitation intervals: {start, end, duration}
    """
    hesitations: List[Dict[str, Any]] = []
    
    if len(phones) < 2:
        return hesitations
    
    # Sort phones by start time
    sorted_phones = sorted(phones, key=lambda p: p.get("start", 0.0))
    
    for i in range(len(sorted_phones) - 1):
        current_end = sorted_phones[i].get("end", 0.0)
        next_start = sorted_phones[i + 1].get("start", 0.0)
        
        gap = next_start - current_end
        
        if gap >= threshold:
            hesitations.append({
                "start": current_end,
                "end": next_start,
                "duration": gap,
            })
    
    return hesitations


def calculate_relative_vowel_duration(
    phones: List[Dict[str, Any]],
    baseline: Dict[str, float],
) -> Dict[str, float]:
    """Calculate vowel duration relative to speaker's baseline.
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        baseline: Speaker baseline dict from analyze_speaker_baseline()
        
    Returns:
        Dict with:
            - median_relative_duration: Median vowel duration / baseline median
            - avg_relative_duration: Average vowel duration / baseline median
            - vowel_count: Number of vowels
    """
    vowels = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", 
              "IH", "IY", "OW", "OY", "UH", "UW"}
    
    vowel_durations: List[float] = []
    baseline_median = baseline.get("median_vowel_duration", 0.10)
    
    for phone in phones:
        label = phone.get("label", "").strip().upper()
        if label in ("SP", "SIL", ""):
            continue
        
        normalized = label.rstrip("012")
        if normalized in vowels:
            duration = phone.get("duration", 0.0)
            if duration > 0:
                relative_duration = duration / baseline_median if baseline_median > 0 else 1.0
                vowel_durations.append(relative_duration)
    
    if not vowel_durations:
        return {
            "median_relative_duration": 1.0,
            "avg_relative_duration": 1.0,
            "vowel_count": 0,
        }
    
    import statistics
    return {
        "median_relative_duration": statistics.median(vowel_durations),
        "avg_relative_duration": statistics.mean(vowel_durations),
        "vowel_count": len(vowel_durations),
    }


def calculate_relative_speech_rate(
    phones: List[Dict[str, Any]],
    baseline: Dict[str, float],
) -> float:
    """Calculate speech rate relative to speaker's baseline.
    
    Args:
        phones: List of phone alignments: {label, start, end, duration}
        baseline: Speaker baseline dict
        
    Returns:
        Relative speech rate (current_rate / baseline_rate)
    """
    baseline_rate = baseline.get("speech_rate", 10.0)
    current_rate = calculate_phone_rate(phones)
    
    if baseline_rate == 0:
        return 1.0
    
    return current_rate / baseline_rate
