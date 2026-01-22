"""Lazy loading of ASR model functions to avoid loading at import time."""
from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # For type hints only


def get_words_timestamps() -> List[Dict[str, Any]]:
    """Lazy import wrapper for words_timestamps to avoid loading model at import time.
    
    Returns:
        List of word-level timestamp dictionaries
    """
    from .pseudo_voice2text import voice2text_word
    return voice2text_word()


def get_char_timestamps() -> List[Dict[str, Any]]:
    """Lazy import wrapper for voice2text_char to avoid loading model at import time.
    
    Returns:
        List of character-level timestamp dictionaries
    """
    from .pseudo_voice2text import voice2text_char
    return voice2text_char()


def get_segment_timestamps() -> List[Dict[str, Any]]:
    """Lazy import wrapper for voice2text_segment to avoid loading model at import time.
    
    Returns:    
        List of segment-level timestamp dictionaries
    """
    from .pseudo_voice2text import voice2text_segment
    return voice2text_segment()
