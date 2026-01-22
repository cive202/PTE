"""Reference text tokenization for alignment."""
from __future__ import annotations

import re
from typing import List

from .normalizer import normalize_token, PAUSE_PUNCTUATION


def tokenize_reference(text: str) -> List[str]:
    """Tokenize reference text, separating punctuation marks as individual tokens.
    
    Example: "Hello, world." -> ["hello", ",", "world", "."]
    
    Args:
        text: The reference text to tokenize
        
    Returns:
        List of tokens (words and punctuation marks)
    """
    tokens = []
    # Split on whitespace first
    raw = re.split(r"\s+", text.strip())
    
    for word in raw:
        if not word:
            continue
        
        # Collect trailing punctuation
        trailing_punct = []
        while word and word[-1] in PAUSE_PUNCTUATION:
            trailing_punct.append(word[-1])
            word = word[:-1]
        
        # Add the word part (if any)
        if word:
            normalized = normalize_token(word)
            if normalized:
                tokens.append(normalized)
        
        # Add trailing punctuation in order (reverse since we collected from end)
        for punct in reversed(trailing_punct):
            tokens.append(punct)
    
    return tokens
