"""CMU Pronouncing Dictionary integration via NLTK."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

try:
    import nltk
    from nltk.corpus import cmudict as nltk_cmudict

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    nltk_cmudict = None  # type: ignore

# Global cache for loaded CMUdict
_CMUDICT_CACHE: Optional[Dict[str, List[List[str]]]] = None


def ensure_cmudict_available() -> bool:
    """Check if CMUdict is available and provide instructions if not.
    
    Returns:
        True if CMUdict is available, False otherwise
    """
    if not NLTK_AVAILABLE:
        return False
    
    try:
        # Try to access CMUdict
        _ = nltk_cmudict.dict()
        return True
    except (LookupError, AttributeError):
        return False


def load_cmudict() -> Dict[str, List[List[str]]]:
    """Load CMU Pronouncing Dictionary via NLTK.
    
    Caches the dictionary after first load for performance.
    
    Returns:
        Dict mapping lowercase words to lists of pronunciations.
        Each pronunciation is a list of ARPAbet phone symbols.
        Example: {"bicycle": [["B", "AY1", "S", "IH0", "K", "AH0", "L"]]}
        
    Raises:
        ImportError: If NLTK is not installed
        LookupError: If CMUdict is not downloaded (with instructions)
    """
    global _CMUDICT_CACHE
    
    if _CMUDICT_CACHE is not None:
        return _CMUDICT_CACHE
    
    if not NLTK_AVAILABLE:
        raise ImportError(
            "NLTK is not installed. Install with: pip install nltk\n"
            "Then download CMUdict: python -c \"import nltk; nltk.download('cmudict')\""
        )
    
    try:
        _CMUDICT_CACHE = nltk_cmudict.dict()
        return _CMUDICT_CACHE
    except LookupError:
        raise LookupError(
            "CMUdict is not downloaded. Run:\n"
            "  python -c \"import nltk; nltk.download('cmudict')\"\n"
            "Or in Python:\n"
            "  import nltk\n"
            "  nltk.download('cmudict')"
        )


def get_word_pronunciation(
    word: str,
    cmu_dict: Optional[Dict[str, List[List[str]]]] = None,
    prefer_first: bool = True,
    pronunciation_index: int = 0,
) -> List[str]:
    """Get pronunciation for a single word from CMUdict.
    
    Args:
        word: Word to look up (case-insensitive)
        cmu_dict: Optional pre-loaded CMUdict (loads if None)
        prefer_first: If True, use first pronunciation (default)
        pronunciation_index: Which pronunciation to use if prefer_first=False
        
    Returns:
        List of ARPAbet phone symbols, or empty list if word not found.
        Example: ["B", "AY1", "S", "IH0", "K", "AH0", "L"] for "bicycle"
    """
    if cmu_dict is None:
        try:
            cmu_dict = load_cmudict()
        except (ImportError, LookupError):
            return []
    
    word_lower = word.lower().strip()
    pronunciations = cmu_dict.get(word_lower, [])
    
    if not pronunciations:
        return []
    
    if prefer_first:
        return pronunciations[0]
    else:
        idx = min(pronunciation_index, len(pronunciations) - 1)
        return pronunciations[idx]


def get_word_phonemes(
    text: str,
    cmu_dict: Optional[Dict[str, List[List[str]]]] = None,
) -> Dict[str, List[str]]:
    """Get phone sequences for each word in text.
    
    Args:
        text: Input text
        cmu_dict: Optional pre-loaded CMUdict
        
    Returns:
        Dict mapping each word to its phone sequence.
        Example: {"bicycle": ["B", "AY1", "S", "IH0", "K", "AH0", "L"], ...}
    """
    if cmu_dict is None:
        try:
            cmu_dict = load_cmudict()
        except (ImportError, LookupError):
            return {}
    
    # Tokenize text (extract words, handle punctuation)
    words = re.findall(r"\b\w+\b", text.lower())
    
    result: Dict[str, List[str]] = {}
    for word in words:
        if word not in result:  # Avoid duplicates
            phones = get_word_pronunciation(word, cmu_dict)
            if phones:
                result[word] = phones
    
    return result


def text_to_phonemes(
    text: str,
    cmu_dict: Optional[Dict[str, List[List[str]]]] = None,
) -> List[str]:
    """Convert text to concatenated phone sequence.
    
    Args:
        text: Input text
        cmu_dict: Optional pre-loaded CMUdict
        
    Returns:
        List of ARPAbet phone symbols for entire text.
        Example: ["B", "AY1", "S", "IH0", "K", "AH0", "L", "R", "EY1", "S", "IH0", "NG"]
    """
    if cmu_dict is None:
        try:
            cmu_dict = load_cmudict()
        except (ImportError, LookupError):
            return []
    
    # Tokenize and get phones for each word
    words = re.findall(r"\b\w+\b", text.lower())
    phonemes: List[str] = []
    
    for word in words:
        word_phones = get_word_pronunciation(word, cmu_dict)
        phonemes.extend(word_phones)
    
    return phonemes
