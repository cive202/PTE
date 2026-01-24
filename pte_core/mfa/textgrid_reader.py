"""TextGrid word-level parsing."""
from __future__ import annotations

from typing import Any, Dict, List

try:
    import textgrid  # type: ignore
except ImportError:
    textgrid = None  # type: ignore


def read_word_textgrid(path: str) -> List[Dict[str, Any]]:
    """Read word-level TextGrid and return list of word alignments.
    
    MFA is a forced aligner - alignment success doesn't mean correct pronunciation.
    Returns status="aligned" (not "correct") to reflect this.
    
    Args:
        path: Path to TextGrid file
        
    Returns:
        List of dicts: {word, start, end, status: "aligned", confidence: None}
        
    Raises:
        ImportError: If textgrid library is not installed
        RuntimeError: If TextGrid cannot be read
    """
    if textgrid is None:
        raise ImportError(
            "textgrid library required. Install with: pip install praat-textgrids"
        )

    try:
        tg = textgrid.TextGrid.fromFile(path)
    except Exception as e:
        raise RuntimeError(f"Failed to read TextGrid: {e}")

    words: List[Dict[str, Any]] = []
    # Find word tier (usually named "words" or similar)
    word_tier = None
    for tier in tg.tiers:
        if tier.name.lower() in ("words", "word", "orthography"):
            word_tier = tier
            break

    if word_tier is None and len(tg.tiers) > 0:
        word_tier = tg.tiers[0]

    if word_tier is None:
        return words

    for interval in word_tier:
        if interval.mark.strip():
            words.append(
                {
                    "word": interval.mark.strip(),
                    "start": float(interval.minTime),
                    "end": float(interval.maxTime),
                    "status": "aligned",  # MFA forced alignment - not pronunciation correctness
                    "confidence": None,  # MFA doesn't provide confidence by default
                }
            )

    return words
