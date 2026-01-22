"""Token normalization utilities for alignment."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # For type hints only


# Punctuation that requires pauses (for PTE scoring)
PAUSE_PUNCTUATION = {",", "."}


def is_punctuation(token: str) -> bool:
    """Check if token is a pause-worthy punctuation mark.
    
    Args:
        token: The token to check
        
    Returns:
        True if token is a pause-worthy punctuation mark (comma or period)
    """
    return token in PAUSE_PUNCTUATION


def normalize_token(token: str, preserve_punctuation: bool = True) -> str:
    """Normalize a token for alignment.
    
    If preserve_punctuation is True, punctuation marks (,.) are preserved as-is.
    Otherwise, all punctuation is stripped.
    
    Args:
        token: The token string to normalize
        preserve_punctuation: If True, preserve comma and period as standalone tokens
        
    Returns:
        Normalized token string (lowercase, stripped, punctuation removed except apostrophes)
    """
    token = token.lower().strip()
    
    # If it's a standalone punctuation mark, preserve it
    if preserve_punctuation and token in PAUSE_PUNCTUATION:
        return token
    
    # keep apostrophes inside words, drop other punctuation
    token = re.sub(r"[^a-z0-9']+", "", token)
    return token
