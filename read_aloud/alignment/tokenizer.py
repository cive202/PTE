"""Reference and transcript tokenization for alignment."""
from __future__ import annotations

import re
from typing import List

from .normalizer import PAUSE_PUNCTUATION


_WORD_OR_PUNCT_RE = re.compile(r"[A-Za-z0-9]+(?:[-'’`´][A-Za-z0-9]+)*|[.,;:!?]")
_APOSTROPHE_TRANSLATION = str.maketrans({
    "’": "'",
    "`": "'",
    "´": "'",
})
_HYPHEN_TRANSLATION = str.maketrans({
    "‐": "-",
    "‑": "-",
    "–": "-",
    "—": "-",
})


def _canonicalize_surface(text: str) -> str:
    text = text.translate(_APOSTROPHE_TRANSLATION)
    text = text.translate(_HYPHEN_TRANSLATION)
    return text


def _split_lexical_token(token: str) -> List[str]:
    """Normalize a lexical token and split hyphen variants into separate words."""
    normalized = token.lower().strip()
    normalized = _canonicalize_surface(normalized)
    parts = normalized.split("-")

    out: List[str] = []
    for part in parts:
        cleaned = re.sub(r"[^a-z0-9']+", "", part)
        if cleaned:
            out.append(cleaned)
    return out


def tokenize_reference(text: str) -> List[str]:
    """Tokenize reference text, separating punctuation marks as individual tokens.
    
    Example: "Hello, world." -> ["hello", ",", "world", "."]
    
    Args:
        text: The reference text to tokenize
        
    Returns:
        List of tokens (words and punctuation marks)
    """
    tokens = []
    raw = _WORD_OR_PUNCT_RE.findall(_canonicalize_surface(text))

    for token in raw:
        if token in PAUSE_PUNCTUATION:
            tokens.append(token)
            continue
        tokens.extend(_split_lexical_token(token))

    return tokens


def tokenize_transcript(text: str) -> List[str]:
    """Tokenize transcript text for lexical comparison.

    Transcript punctuation is ignored as lexical evidence.
    Hyphenated variants are split into separate lexical tokens.
    """
    tokens: List[str] = []
    raw = _WORD_OR_PUNCT_RE.findall(_canonicalize_surface(text))

    for token in raw:
        if token in PAUSE_PUNCTUATION:
            continue
        tokens.extend(_split_lexical_token(token))

    return tokens
