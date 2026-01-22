"""Data model for aligned words between reference and ASR output."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AlignedWord:
    """Represents an aligned word between reference text and ASR output.
    
    Attributes:
        ref_word: The word from the reference text (or None if not in reference)
        hyp_word: The word from ASR hypothesis (or None if not in ASR)
        op: Operation type - "match", "sub", "del", or "ins"
        hyp_start: Start timestamp from ASR (or None)
        hyp_end: End timestamp from ASR (or None)
    """
    ref_word: Optional[str]
    hyp_word: Optional[str]
    op: str  # "match" | "sub" | "del" | "ins"
    hyp_start: Optional[float] = None
    hyp_end: Optional[float] = None
