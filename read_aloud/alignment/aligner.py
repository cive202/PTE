"""Alignment orchestration between reference text and ASR output."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from read_aloud.models.aligned_word import AlignedWord
from .edit_distance import align_sequences
from .normalizer import normalize_token
from .tokenizer import tokenize_reference


def tokenize_asr(asr_words: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Tokenize ASR output, preserving punctuation as separate tokens.
    Returns:
        - hyp_tokens: List of normalized tokens (words and punctuation)
        - hyp_entries: List of corresponding ASR entries with timestamps
    """
    hyp_tokens: List[str] = []
    hyp_entries: List[Dict[str, Any]] = []
    
    for w in asr_words:
        # Handle both formats:
        # Old: {"word": "...", "start": ..., "end": ...}
        # New: {"type": "word", "value": "...", "start": ..., "end": ...}
        raw_word = w.get("word") or w.get("value", "")
        normalized = normalize_token(raw_word)
        if normalized:
            hyp_tokens.append(normalized)
            hyp_entries.append(w)
    
    return hyp_tokens, hyp_entries


def align_reference_to_asr(
    reference_text: str, asr_words: List[Dict[str, Any]]
) -> List[AlignedWord]:
    """Align reference tokens to ASR word list (each item like {start,end,word}).
    
    Now includes punctuation tokens for pause detection.
    
    Args:
        reference_text: The reference text to align
        asr_words: List of ASR word entries with timestamps
        
    Returns:
        List of AlignedWord objects representing the alignment
    """
    ref_tokens = tokenize_reference(reference_text)
    hyp_tokens, hyp_entries = tokenize_asr(asr_words)

    ops = align_sequences(ref_tokens, hyp_tokens)
    aligned: List[AlignedWord] = []
    for op, ri, hj in ops:
        ref_word = ref_tokens[ri] if ri is not None else None
        hyp_word = hyp_tokens[hj] if hj is not None else None
        hyp_start = hyp_entries[hj].get("start") if hj is not None else None
        hyp_end = hyp_entries[hj].get("end") if hj is not None else None
        aligned.append(AlignedWord(ref_word=ref_word, hyp_word=hyp_word, op=op, hyp_start=hyp_start, hyp_end=hyp_end))
    return aligned
