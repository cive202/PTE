"""Phone duration-based pronunciation scoring with accent tolerance."""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

try:
    from phonetics.accent_tolerance import (
        FINAL_VOICELESS_STOPS,
        find_best_match,
        is_accent_equivalent,
        phoneme_similarity,
    )
    from phonetics.cmudict import get_word_pronunciation
    from phonetics.phone_mapper import convert_phone_sequence
    ACCENT_TOLERANCE_AVAILABLE = True
    CMUDICT_AVAILABLE = True
except ImportError:
    ACCENT_TOLERANCE_AVAILABLE = False
    CMUDICT_AVAILABLE = False
    FINAL_VOICELESS_STOPS = set()  # type: ignore
    get_word_pronunciation = None  # type: ignore
    convert_phone_sequence = None  # type: ignore
    phoneme_similarity = None  # type: ignore
    is_accent_equivalent = None  # type: ignore
    find_best_match = None  # type: ignore

try:
    from .phoneme_alignment import (
        align_phonemes_with_dp,
        calculate_intelligibility_score,
    )
    ALIGNMENT_AVAILABLE = True
except ImportError:
    ALIGNMENT_AVAILABLE = False
    align_phonemes_with_dp = None  # type: ignore
    calculate_intelligibility_score = None  # type: ignore

try:
    from .accent_config import STRESS_PENALTY_MAX
    from .speaker_normalization import (
        _is_consonant,
        _is_vowel,
        normalize_timing,
    )
    ACCENT_CONFIG_AVAILABLE = True
except ImportError:
    ACCENT_CONFIG_AVAILABLE = False
    STRESS_PENALTY_MAX = 0.5  # Default fallback
    normalize_timing = None  # type: ignore
    _is_vowel = None  # type: ignore
    _is_consonant = None  # type: ignore


# Expected phone durations (in seconds) - approximate values for English
# These should be calibrated with native speaker data
# Updated with higher precision values
EXPECTED_PHONE_DURATIONS: Dict[str, float] = {
    "AA": 0.125, "AE": 0.110, "AH": 0.095, "AO": 0.120, "AW": 0.160,
    "AY": 0.155, "EH": 0.105, "ER": 0.115, "EY": 0.130, "IH": 0.085,
    "IY": 0.125, "OW": 0.135, "OY": 0.170, "UH": 0.090, "UW": 0.130,
    "B": 0.045, "CH": 0.090, "D": 0.050, "DH": 0.045, "F": 0.070,
    "G": 0.055, "HH": 0.060, "JH": 0.095, "K": 0.065, "L": 0.075,
    "M": 0.070, "N": 0.065, "NG": 0.085, "P": 0.060, "R": 0.070,
    "S": 0.085, "SH": 0.095, "T": 0.055, "TH": 0.075, "V": 0.065,
    "W": 0.060, "Y": 0.060, "Z": 0.065, "ZH": 0.085,
}

# Standard deviations for phone durations
# Some phones are naturally more variable (e.g., vowels) than others (stops)
PHONE_DURATION_STD: Dict[str, float] = {
    phone: duration * 0.25  # Tighter variance (25%) than before
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
    baseline: Optional[Dict[str, float]] = None,
    accent_tolerant: bool = True,
) -> Dict[str, Any]:
    """Score pronunciation quality based on phone durations with accent tolerance.
    
    Heuristics (accent-tolerant):
    - Phone duration z-score: |z| > 2 → penalty (relative to speaker baseline if provided)
    - Missing stressed vowels → light penalty (max 30% for stress errors)
    - Consonant cluster collapse detection (using similarity matching)
    - Accent-equivalent substitutions accepted (TH→T, V→W, etc.)
    
    Args:
        word: Word being analyzed
        phones: List of phone alignments: {label, start, end, duration}
        reference_phones: Expected phone sequence (optional, for cluster detection)
        cmu_dict: Optional CMUdict dictionary (used if reference_phones is None)
        baseline: Optional speaker baseline dict (for relative timing)
        accent_tolerant: Whether to use accent-tolerant scoring (default: True)
        
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
        
        # Get expected duration - use relative timing if baseline provided
        if baseline and accent_tolerant and normalize_timing:
            # Use speaker-relative timing
            expected_duration = EXPECTED_PHONE_DURATIONS.get(normalized_label, 0.08)
            expected_std = PHONE_DURATION_STD.get(normalized_label, expected_duration * 0.25)
            
            z = normalize_timing(
                phone_duration=duration,
                phone_label=label,
                baseline=baseline,
                native_expected=expected_duration,
                native_std=expected_std,
            )
            z_scores.append(abs(z))
        else:
            # Use absolute timing (native model)
            expected_duration = EXPECTED_PHONE_DURATIONS.get(normalized_label, 0.08)
            expected_std = PHONE_DURATION_STD.get(normalized_label, expected_duration * 0.25)
            z = _calculate_z_score(duration, expected_duration, expected_std)
            z_scores.append(abs(z))
        
        # Check for duration outliers
        if abs(z) > 2.0:
            if duration < (EXPECTED_PHONE_DURATIONS.get(normalized_label, 0.08) if not baseline else 
                          (baseline.get("median_vowel_duration", 0.10) if _is_vowel and _is_vowel(label) else
                           baseline.get("median_consonant_duration", 0.06))):
                if _is_stressed_vowel(label):
                    issues.append("stressed_vowel_shortened")
                    stressed_vowel_durations.append(duration)
                else:
                    issues.append("phone_shortened")
            else:
                issues.append("phone_lengthened")
        
        # Check for missing stressed vowels (only if not using relative timing)
        if not baseline and _is_stressed_vowel(label):
            expected_duration = EXPECTED_PHONE_DURATIONS.get(normalized_label, 0.10)
            if duration < expected_duration * 0.5:
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
    
    # Detect consonant cluster collapse using similarity-based matching
    if reference_phones:
        observed_labels = [_normalize_phone_label(p.get("label", "")) for p in phones]
        expected_labels = [_normalize_phone_label(p) for p in reference_phones]
        
        if accent_tolerant and ACCENT_TOLERANCE_AVAILABLE and find_best_match and is_accent_equivalent:
            # Use similarity-based matching (accent-tolerant)
            matched_expected = set()
            unmatched_expected = []
            
            for expected_phone in expected_labels:
                best_match, similarity = find_best_match(expected_phone, observed_labels)
                if best_match and similarity >= 0.6:  # Accept accent-equivalent
                    matched_expected.add(expected_phone)
                else:
                    unmatched_expected.append(expected_phone)
            
            # Check for truly missing phones (not accent-equivalent)
            missing_phones = unmatched_expected
        else:
            # Exact matching (old behavior)
            expected_set = set(expected_labels)
            observed_set = set(observed_labels)
            missing_phones = list(expected_set - observed_set)
        
        if missing_phones:
            # Check if missing phones are consonants (likely cluster collapse)
            consonants = {"B", "CH", "D", "DH", "F", "G", "HH", "JH", "K", "L", 
                         "M", "N", "NG", "P", "R", "S", "SH", "T", "TH", "V", 
                         "W", "Y", "Z", "ZH"}
            missing_consonants = [p for p in missing_phones if p in consonants]
            
            # Check for final-consonant deletion (common in many accents)
            # Final voiceless stops (T, K, P) can be dropped with reduced penalty
            # Example: "worked" → W ER K T (expected) vs W ER K (actual)
            # Note: Voiced stops (D, B, G) are NOT included - they affect intelligibility more
            final_stop_deletions = []
            if reference_phones and ACCENT_TOLERANCE_AVAILABLE and FINAL_VOICELESS_STOPS:
                # Check if missing phone is final and is a voiceless stop
                for missing_phone in missing_consonants:
                    normalized_missing = _normalize_phone_label(missing_phone)
                    # Check if it's the last expected phone (final position)
                    if reference_phones:
                        last_expected = _normalize_phone_label(reference_phones[-1])
                        if normalized_missing == last_expected and normalized_missing in FINAL_VOICELESS_STOPS:
                            final_stop_deletions.append(missing_phone)
            
            if missing_consonants:
                # Mark as consonant_missing, but note if it's a final stop
                issues.append("consonant_missing")
                if final_stop_deletions:
                    issues.append("final_stop_deletion")  # Special marker for reduced penalty
                # Check for cluster collapse pattern (consecutive missing consonants)
                if len(missing_consonants) > 1:
                    issues.append("consonant_cluster_collapse")
    
    # Calculate quality score using alignment-based intelligibility (if available)
    # This is the PTE-style approach: intelligibility-weighted alignment
    alignment_score = None
    if reference_phones and ALIGNMENT_AVAILABLE and align_phonemes_with_dp and calculate_intelligibility_score:
        try:
            observed_labels = [_normalize_phone_label(p.get("label", "")) for p in phones]
            expected_labels = [_normalize_phone_label(p) for p in reference_phones]
            
            # Filter out silence/SP phones from observed
            observed_labels = [p for p in observed_labels if p and p not in ("SP", "SIL")]
            
            if observed_labels and expected_labels:
                alignment_path, total_cost, metadata = align_phonemes_with_dp(
                    expected_labels,
                    observed_labels,
                    word=word,
                    accent_tolerant=accent_tolerant,
                )
                alignment_score = calculate_intelligibility_score(alignment_path, metadata)
        except Exception:
            # Fallback to duration-based scoring if alignment fails
            pass
    
    # Base score: inverse of average z-score (clamped to 0-1)
    # Use alignment score if available, otherwise fall back to duration-based
    if alignment_score is not None:
        base_score = alignment_score
    elif z_scores:
        avg_z = statistics.mean(z_scores)
        base_score = max(0.0, min(1.0, 1.0 - (avg_z / 4.0)))  # Normalize to 0-1
    else:
        base_score = 1.0
    
    # Apply penalties (accent-tolerant)
    if accent_tolerant and ACCENT_CONFIG_AVAILABLE:
        # Light penalty for stress errors (max 30%)
        stress_penalty = 0.0
        if "stressed_vowel_missing" in issues:
            stress_penalty = min(STRESS_PENALTY_MAX, 0.2)  # 20% for missing
        elif "stressed_vowel_shortened" in issues:
            stress_penalty = min(STRESS_PENALTY_MAX, 0.15)  # 15% for shortened
        
        base_score *= (1.0 - stress_penalty)
        
        # Moderate penalty for missing consonants (if not accent-equivalent)
        if "consonant_missing" in issues:
            if "final_stop_deletion" in issues:
                # Final voiceless stop deletion: reduce penalty by 50%
                # Common in many accents (e.g., "worked" → "work")
                base_score *= 0.925  # Only 7.5% penalty (50% reduction)
            else:
                base_score *= 0.85  # 15% penalty (reduced from 30%)
    else:
        # Old behavior (heavier penalties)
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
