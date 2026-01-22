"""Phone duration-based pronunciation scoring."""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

try:
    from ..phonetics.cmudict import get_word_pronunciation
    from ..phonetics.phone_mapper import convert_phone_sequence
    CMUDICT_AVAILABLE = True
except ImportError:
    CMUDICT_AVAILABLE = False
    get_word_pronunciation = None  # type: ignore
    convert_phone_sequence = None  # type: ignore


# Expected phone durations (in seconds) - approximate values for English
# These should be calibrated with native speaker data
EXPECTED_PHONE_DURATIONS: Dict[str, float] = {
    # Vowels (longer)
    "AA": 0.12, "AE": 0.10, "AH": 0.10, "AO": 0.12, "AW": 0.15,
    "AY": 0.15, "EH": 0.10, "ER": 0.12, "EY": 0.12, "IH": 0.08,
    "IY": 0.12, "OW": 0.12, "OY": 0.15, "UH": 0.08, "UW": 0.12,
    # Consonants (shorter)
    "B": 0.05, "CH": 0.08, "D": 0.05, "DH": 0.05, "F": 0.06,
    "G": 0.05, "HH": 0.05, "JH": 0.08, "K": 0.05, "L": 0.06,
    "M": 0.06, "N": 0.06, "NG": 0.08, "P": 0.05, "R": 0.06,
    "S": 0.06, "SH": 0.08, "T": 0.05, "TH": 0.06, "V": 0.06,
    "W": 0.06, "Y": 0.06, "Z": 0.06, "ZH": 0.08,
}

# Standard deviations for phone durations
PHONE_DURATION_STD: Dict[str, float] = {
    phone: duration * 0.3  # 30% coefficient of variation
    for phone, duration in EXPECTED_PHONE_DURATIONS.items()
}

# Stressed vowel markers (for English)
STRESSED_VOWELS = {"AA1", "AE1", "AH1", "AO1", "AW1", "AY1", "EH1", "ER1", 
                   "EY1", "IH1", "IY1", "OW1", "OY1", "UH1", "UW1"}


def _normalize_phone_label(label: str) -> str:
    """Normalize phone label (remove stress markers, convert to uppercase)."""
    # Remove stress markers (0, 1, 2) and convert to uppercase
    normalized = label.upper().rstrip("012")
    return normalized


def _is_stressed_vowel(label: str) -> bool:
    """Check if phone is a stressed vowel."""
    return label.upper() in STRESSED_VOWELS or label.upper().endswith("1")


def _calculate_z_score(observed: float, expected: float, std: float) -> float:
    """Calculate z-score for phone duration.
    
    Args:
        observed: Observed duration
        expected: Expected duration
        std: Standard deviation
        
    Returns:
        Z-score
    """
    if std == 0:
        return 0.0
    return (observed - expected) / std


def score_pronunciation_from_phones(
    word: str,
    phones: List[Dict[str, Any]],
    reference_phones: Optional[List[str]] = None,
    cmu_dict: Optional[Any] = None,
) -> Dict[str, Any]:
    """Score pronunciation quality based on phone durations.
    
    Heuristics:
    - Phone duration z-score: |z| > 2 → penalty
    - Missing stressed vowels → mispronounced (high correlation with PTE score)
    - Consonant cluster collapse detection
    
    Args:
        word: Word being analyzed
        phones: List of phone alignments: {label, start, end, duration}
        reference_phones: Expected phone sequence (optional, for cluster detection)
        cmu_dict: Optional CMUdict dictionary (used if reference_phones is None)
        
    Returns:
        Dict with:
            - quality_score: float (0.0 = worst, 1.0 = best)
            - issues: List[str] (e.g., ["vowel_shortened", "consonant_missing"])
            - confidence: float (same as quality_score)
    """
    if not phones:
        return {
            "quality_score": 0.0,
            "issues": ["no_phones"],
            "confidence": 0.0,
        }

    issues: List[str] = []
    z_scores: List[float] = []
    stressed_vowel_durations: List[float] = []
    
    # Analyze each phone
    for phone in phones:
        label = phone.get("label", "").strip()
        if not label or label.upper() in ("SP", "SIL"):
            continue
        
        duration = phone.get("duration", 0.0)
        normalized_label = _normalize_phone_label(label)
        
        # Get expected duration
        expected_duration = EXPECTED_PHONE_DURATIONS.get(normalized_label, 0.08)  # Default
        expected_std = PHONE_DURATION_STD.get(normalized_label, 0.02)  # Default
        
        # Calculate z-score
        z = _calculate_z_score(duration, expected_duration, expected_std)
        z_scores.append(abs(z))
        
        # Check for duration outliers
        if abs(z) > 2.0:
            if duration < expected_duration:
                if _is_stressed_vowel(label):
                    issues.append("stressed_vowel_shortened")
                    stressed_vowel_durations.append(duration)
                else:
                    issues.append("phone_shortened")
            else:
                issues.append("phone_lengthened")
        
        # Check for missing stressed vowels
        if _is_stressed_vowel(label) and duration < expected_duration * 0.5:
            issues.append("stressed_vowel_missing")
    
    # Get reference phones from CMUdict if not provided
    if reference_phones is None and CMUDICT_AVAILABLE and get_word_pronunciation and convert_phone_sequence:
        try:
            # Get ARPAbet phones from CMUdict
            arpabet_phones = get_word_pronunciation(word, cmu_dict)
            if arpabet_phones:
                # Convert ARPAbet to MFA format
                reference_phones = convert_phone_sequence(arpabet_phones)
        except Exception:
            # Fallback: continue without reference phones
            pass
    
    # Detect consonant cluster collapse
    if reference_phones:
        observed_labels = [_normalize_phone_label(p.get("label", "")) for p in phones]
        expected_labels = [_normalize_phone_label(p) for p in reference_phones]
        
        # Check for missing phones (especially in clusters)
        expected_set = set(expected_labels)
        observed_set = set(observed_labels)
        missing_phones = expected_set - observed_set
        
        if missing_phones:
            # Check if missing phones are consonants (likely cluster collapse)
            consonants = {"B", "CH", "D", "DH", "F", "G", "HH", "JH", "K", "L", 
                         "M", "N", "NG", "P", "R", "S", "SH", "T", "TH", "V", 
                         "W", "Y", "Z", "ZH"}
            missing_consonants = [p for p in missing_phones if p in consonants]
            if missing_consonants:
                issues.append("consonant_missing")
                # Check for cluster collapse pattern (consecutive missing consonants)
                if len(missing_consonants) > 1:
                    issues.append("consonant_cluster_collapse")
    
    # Calculate quality score
    # Base score: inverse of average z-score (clamped to 0-1)
    if z_scores:
        avg_z = statistics.mean(z_scores)
        base_score = max(0.0, min(1.0, 1.0 - (avg_z / 4.0)))  # Normalize to 0-1
    else:
        base_score = 1.0
    
    # Penalize for critical issues
    if "stressed_vowel_missing" in issues or "stressed_vowel_shortened" in issues:
        base_score *= 0.5  # Heavy penalty
    
    if "consonant_missing" in issues:
        base_score *= 0.7  # Moderate penalty
    
    quality_score = max(0.0, min(1.0, base_score))
    
    return {
        "quality_score": quality_score,
        "issues": issues,
        "confidence": quality_score,  # Use quality score as confidence
    }
