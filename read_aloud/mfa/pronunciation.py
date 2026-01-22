"""Main API for MFA-based pronunciation assessment."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .aligner import align_with_mfa
from .asr_aligner import align_mfa_to_asr
from .scorer import score_pronunciation_from_phones
from .timing_metrics import (
    calculate_phone_rate,
    calculate_vowel_ratio,
    calculate_word_duration,
    detect_hesitation,
)

try:
    from ..phonetics.cmudict import load_cmudict, ensure_cmudict_available
    CMUDICT_AVAILABLE = True
except ImportError:
    CMUDICT_AVAILABLE = False
    load_cmudict = None  # type: ignore
    ensure_cmudict_available = None  # type: ignore


def assess_pronunciation_mfa(
    wav_path: str,
    reference_text: str,
    *,
    confidence_threshold: float = 0.75,
    acoustic_model: str = "english_us_arpa",
    dictionary: str = "english_us_arpa",
    asr_words: Optional[List[Dict[str, Any]]] = None,
    use_cmudict: bool = True,
) -> List[Dict[str, Any]]:
    """Use MFA to assess pronunciation and return word-level results with phone-level analysis.
    
    MFA is a forced aligner - it provides precise timestamps and phone-level alignment,
    but cannot detect missed words or judge correctness. This function uses phone
    duration analysis to assess pronunciation quality.
    
    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription
        confidence_threshold: Threshold for pronunciation quality score (default: 0.75)
        acoustic_model: MFA acoustic model name
        dictionary: MFA dictionary name
        asr_words: Optional ASR word alignments for MFA+ASR integration
        use_cmudict: Whether to use CMUdict for expected phones (default: True)
        
    Returns:
        List of dicts with:
            - word: str
            - start: float
            - end: float
            - status: "aligned" | "mispronounced" (based on phone analysis)
            - confidence: float (real quality score from phone analysis, 0.0-1.0)
            - phone_quality_score: float
            - timing_metrics: Dict[str, float]
            - issues: List[str] (e.g., ["vowel_shortened", "consonant_missing"])
    """
    # Run MFA alignment with phone-level data
    alignment_result = align_with_mfa(
        wav_path,
        reference_text,
        acoustic_model=acoustic_model,
        dictionary=dictionary,
        include_phones=True,
    )
    
    mfa_words = alignment_result.get("words", [])
    phones = alignment_result.get("phones", [])
    
    # Group phones by word (simplified - assumes phones are in word order)
    # In practice, you'd need word-to-phone mapping from MFA output
    word_phones: Dict[int, List[Dict[str, Any]]] = {}
    phone_idx = 0
    
    for word_idx, word_align in enumerate(mfa_words):
        word_start = word_align.get("start")
        word_end = word_align.get("end")
        
        if word_start is None or word_end is None:
            continue
        
        word_phones[word_idx] = []
        while phone_idx < len(phones):
            phone = phones[phone_idx]
            phone_start = phone.get("start", 0.0)
            phone_end = phone.get("end", 0.0)
            
            # Check if phone overlaps with word
            if phone_start >= word_start and phone_end <= word_end:
                word_phones[word_idx].append(phone)
                phone_idx += 1
            elif phone_start > word_end:
                break
            else:
                phone_idx += 1
    
    # Calculate timing metrics for entire utterance
    timing_metrics = {
        "word_duration": calculate_word_duration(mfa_words),
        "phone_rate": calculate_phone_rate(phones),
        "vowel_ratio": calculate_vowel_ratio(phones),
        "hesitations": detect_hesitation(phones),
    }
    
    # Load CMUdict if requested and available
    cmu_dict = None
    if use_cmudict and CMUDICT_AVAILABLE and ensure_cmudict_available and load_cmudict:
        try:
            if ensure_cmudict_available():
                cmu_dict = load_cmudict()
        except Exception:
            # Fallback: continue without CMUdict
            pass
    
    # Assess pronunciation for each word
    results: List[Dict[str, Any]] = []
    
    for word_idx, word_align in enumerate(mfa_words):
        word = word_align.get("word", "")
        word_phone_list = word_phones.get(word_idx, [])
        
        # Score pronunciation based on phone durations
        phone_score_result = score_pronunciation_from_phones(
            word,
            word_phone_list,
            reference_phones=None,  # Will be filled from CMUdict if available
            cmu_dict=cmu_dict,
        )
        
        quality_score = phone_score_result.get("quality_score", 1.0)
        issues = phone_score_result.get("issues", [])
        
        # Determine status based on quality score
        status = "mispronounced" if quality_score < confidence_threshold else "aligned"
        
        result: Dict[str, Any] = {
            "word": word,
            "start": word_align.get("start"),
            "end": word_align.get("end"),
            "status": status,
            "confidence": quality_score,  # Real quality score, not fake
            "phone_quality_score": quality_score,
            "timing_metrics": timing_metrics,  # Shared across all words
            "issues": issues,
        }
        
        # Add MFA+ASR alignment if ASR words provided
        if asr_words:
            aligned = align_mfa_to_asr([word_align], asr_words)
            if aligned:
                result.update({
                    "asr_aligned": aligned[0].get("asr_aligned", False),
                    "asr_word": aligned[0].get("asr_word"),
                    "overlap_duration": aligned[0].get("overlap_duration", 0.0),
                    "pronunciation_driven_substitution": aligned[0].get(
                        "pronunciation_driven_substitution", False
                    ),
                })
        
        results.append(result)
    
    return results
