"""MFA+ASR timeline alignment integration."""
from __future__ import annotations

from typing import Any, Dict, List


def _normalize_text(text: str) -> str:
    """Normalize text for matching (lowercase, strip punctuation)."""
    import re
    normalized = text.lower().strip()
    # Remove punctuation
    normalized = re.sub(r"[^\w\s]", "", normalized)
    return normalized


def align_mfa_to_asr(
    mfa_words: List[Dict[str, Any]],
    asr_words: List[Dict[str, Any]],
    overlap_threshold: float = 0.1,
) -> List[Dict[str, Any]]:
    """Align MFA words to ASR words using normalized text and time overlap.
    
    Algorithm:
    - Normalize text for matching
    - Calculate time overlap: overlap = min(mfa_end, asr_end) - max(mfa_start, asr_start)
    - If overlap < threshold → ASR substitution likely pronunciation-driven
    - Map MFA words to ASR words using normalized text + time overlap
    
    Args:
        mfa_words: MFA word alignments: {word, start, end, ...}
        asr_words: ASR word alignments: {word, start, end, ...}
        overlap_threshold: Minimum overlap duration to consider aligned (seconds)
        
    Returns:
        MFA words with ASR alignment metadata:
        {
            "word": str,
            "start": float,
            "end": float,
            "asr_aligned": bool,
            "asr_word": Optional[str],
            "overlap_duration": float,
            "pronunciation_driven_substitution": bool,
        }
    """
    aligned_mfa_words: List[Dict[str, Any]] = []
    
    # Create normalized lookup for ASR words
    asr_lookup: Dict[str, List[Dict[str, Any]]] = {}
    for asr_word in asr_words:
        normalized = _normalize_text(asr_word.get("word", ""))
        if normalized:
            if normalized not in asr_lookup:
                asr_lookup[normalized] = []
            asr_lookup[normalized].append(asr_word)
    
    for mfa_word in mfa_words:
        mfa_text = mfa_word.get("word", "")
        mfa_start = mfa_word.get("start")
        mfa_end = mfa_word.get("end")
        
        normalized_mfa = _normalize_text(mfa_text)
        
        result: Dict[str, Any] = {
            "word": mfa_text,
            "start": mfa_start,
            "end": mfa_end,
            "asr_aligned": False,
            "asr_word": None,
            "overlap_duration": 0.0,
            "pronunciation_driven_substitution": False,
        }
        
        # Try to find matching ASR word
        if normalized_mfa in asr_lookup and mfa_start is not None and mfa_end is not None:
            # Find best matching ASR word by time overlap
            best_overlap = 0.0
            best_asr_word = None
            
            for asr_word in asr_lookup[normalized_mfa]:
                asr_start = asr_word.get("start")
                asr_end = asr_word.get("end")
                
                if asr_start is not None and asr_end is not None:
                    # Calculate overlap
                    overlap_start = max(mfa_start, asr_start)
                    overlap_end = min(mfa_end, asr_end)
                    overlap = max(0.0, overlap_end - overlap_start)
                    
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_asr_word = asr_word
            
            if best_overlap >= overlap_threshold:
                result["asr_aligned"] = True
                result["asr_word"] = best_asr_word.get("word") if best_asr_word else None
                result["overlap_duration"] = best_overlap
            else:
                # Low overlap suggests pronunciation-driven substitution
                result["pronunciation_driven_substitution"] = True
        else:
            # No matching ASR word found - could be insertion or substitution
            # Check for nearby ASR words with low overlap
            if mfa_start is not None and mfa_end is not None:
                for asr_word in asr_words:
                    asr_start = asr_word.get("start")
                    asr_end = asr_word.get("end")
                    
                    if asr_start is not None and asr_end is not None:
                        overlap_start = max(mfa_start, asr_start)
                        overlap_end = min(mfa_end, asr_end)
                        overlap = max(0.0, overlap_end - overlap_start)
                        
                        if 0 < overlap < overlap_threshold:
                            result["pronunciation_driven_substitution"] = True
                            result["overlap_duration"] = overlap
                            break
        
        aligned_mfa_words.append(result)
    
    return aligned_mfa_words
