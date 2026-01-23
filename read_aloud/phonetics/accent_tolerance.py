"""Accent-tolerant phoneme matching for pronunciation assessment."""
from __future__ import annotations

from typing import Dict, Tuple


# Phoneme similarity table for accent-equivalent substitutions
# IMPORTANT: This is DIRECTIONAL (expected -> actual), not symmetric
# Values: (expected, actual) -> similarity_score (0.0-1.0)
# 1.0 = exact match, 0.7-0.9 = acceptable accent substitution, 0.0 = different
# 
# Key principle: Accent tolerance is expectation-driven
# Expected TH, actual T → acceptable (0.7)
# Expected T, actual TH → not equivalent (0.0, unless explicitly defined)
PHONEME_SIMILARITY: Dict[Tuple[str, str], float] = {
    # TH substitutions (very common in many accents)
    # Directional: TH -> T/D is acceptable, but T -> TH is not equivalent
    ("TH", "T"): 0.7,  # "think" → "tink" (common in Indian/Nepali)
    ("TH", "D"): 0.7,  # "this" → "dis" (common in many accents)
    ("TH", "S"): 0.6,  # Less common but acceptable
    ("TH", "F"): 0.5,  # Less acceptable
    
    # V/W substitutions
    ("V", "W"): 0.8,  # "very" → "wery" (common in many accents)
    # Note: W -> V is less common, not included (directional)
    
    # Z/S substitutions
    ("Z", "S"): 0.8,  # "zoo" → "soo" (common in many accents)
    ("Z", "J"): 0.7,  # "zoo" → "joo" (some accents)
    # Note: S -> Z is less common, not included (directional)
    
    # R/L substitutions (context-dependent, partial acceptance)
    ("R", "L"): 0.6,  # "red" → "led" (some accents, context matters)
    # Note: L -> R is less common, not included (directional)
    
    # IH/IY merging (common in many accents)
    ("IH", "IY"): 0.7,  # "bit" → "beat" (merged in many accents)
    ("IY", "IH"): 0.7,  # Reverse acceptable (vowel merging is bidirectional)
    ("IH", "EH"): 0.6,  # Less common
    
    # Vowel substitutions (accent-dependent, bidirectional for vowels)
    # NOTE: Bidirectionality is allowed only for vowel quality mergers,
    # not for consonants or manner changes. This reflects that vowel
    # quality variations are often systematic accent features.
    ("AE", "EH"): 0.7,  # "cat" → "ket" (some accents)
    ("EH", "AE"): 0.7,  # Vowel substitutions often bidirectional
    ("AH", "AA"): 0.7,  # "but" → "bat" (some accents)
    ("AA", "AH"): 0.7,  # Vowel substitutions often bidirectional
    
    # Consonant cluster simplifications
    ("NG", "N"): 0.6,  # Final -ing → -in (common in many accents)
    # Note: N -> NG is less common, not included (directional)
    
    # Fricative substitutions
    ("SH", "S"): 0.7,  # "ship" → "sip" (some accents)
    ("ZH", "Z"): 0.7,  # "measure" → "mezure"
    ("CH", "T"): 0.6,  # "chair" → "tair" (less common)
    ("JH", "D"): 0.6,  # "judge" → "dudge"
}

# Vowels set for vowel-weighted cost calculation
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", 
          "IH", "IY", "OW", "OY", "UH", "UW"}

# Final stops that can be dropped (common in many accents)
# Split by voicing because voiceless stops are dropped more frequently
# and with less intelligibility impact than voiced stops.
FINAL_VOICELESS_STOPS = {"T", "K", "P"}  # Very common, heavy discount
FINAL_VOICED_STOPS = {"D", "B", "G"}     # Less common, light/no discount

# Legacy alias for backward compatibility (use FINAL_VOICELESS_STOPS for new code)
FINAL_STOPS = FINAL_VOICELESS_STOPS

# Minimum similarity threshold to accept as accent-equivalent
PHONEME_SIMILARITY_THRESHOLD = 0.6


def phoneme_similarity(expected: str, actual: str) -> float:
    """Calculate similarity between expected and actual phone.
    
    DIRECTIONAL: Only checks (expected -> actual), not reverse.
    This is expectation-driven accent tolerance.
    
    Returns 1.0 for exact match, similarity score (0.0-1.0) for 
    accent-equivalent substitutions, 0.0 for completely different phones.
    
    Args:
        expected: Expected phone symbol (from CMUdict)
        actual: Actual phone symbol (from MFA/WavLM)
        
    Returns:
        Similarity score (0.0-1.0)
    """
    # Normalize (uppercase, remove stress markers for comparison)
    expected_norm = expected.upper().rstrip("012")
    actual_norm = actual.upper().rstrip("012")
    
    # Exact match
    if expected_norm == actual_norm:
        return 1.0
    
    # Check similarity table (DIRECTIONAL - only expected -> actual)
    similarity = PHONEME_SIMILARITY.get((expected_norm, actual_norm), 0.0)
    
    # No reverse lookup - accent tolerance is expectation-driven
    # This prevents "over-forgiving" errors
    
    return similarity


def phoneme_cost(expected: str, actual: str) -> float:
    """Calculate alignment cost between expected and actual phone.
    
    Vowel quality matters more than consonants in PTE scoring.
    This function applies vowel-weighted cost.
    
    Used in sequence alignment algorithms. Lower cost = better match.
    
    Args:
        expected: Expected phone symbol
        actual: Actual phone symbol
        
    Returns:
        Cost (0.0 = perfect match, higher for vowels, lower for consonants)
    """
    similarity = phoneme_similarity(expected, actual)
    base_cost = 1.0 - similarity
    
    # Vowel quality matters more than consonants
    # PTE penalizes vowel errors more heavily
    expected_base = expected.upper().rstrip("012")
    if expected_base in VOWELS:
        return base_cost * 1.2  # Vowels hurt 20% more
    return base_cost


def is_accent_equivalent(expected: str, actual: str) -> bool:
    """Check if actual phone is accent-equivalent to expected.
    
    IMPORTANT: This function is for DIAGNOSTICS and FEEDBACK only.
    Do NOT use this boolean gate inside alignment algorithms (DP, edit distance).
    Use phoneme_cost() instead, which provides continuous costs for stable alignment.
    
    Args:
        expected: Expected phone symbol
        actual: Actual phone symbol
        
    Returns:
        True if similarity >= threshold, False otherwise
    """
    similarity = phoneme_similarity(expected, actual)
    return similarity >= PHONEME_SIMILARITY_THRESHOLD


def find_best_match(expected_phone: str, observed_phones: list[str]) -> tuple[str | None, float]:
    """Find best matching observed phone for expected phone.
    
    Args:
        expected_phone: Expected phone symbol
        observed_phones: List of observed phone symbols
        
    Returns:
        Tuple of (best_match_phone, similarity_score)
        Returns (None, 0.0) if no good match found
    """
    best_match = None
    best_similarity = 0.0
    
    for observed in observed_phones:
        similarity = phoneme_similarity(expected_phone, observed)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = observed
    
    if best_similarity >= PHONEME_SIMILARITY_THRESHOLD:
        return (best_match, best_similarity)
    
    return (None, best_similarity)
