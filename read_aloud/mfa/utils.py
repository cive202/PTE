"""File I/O helpers and model caching utilities."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def write_text_file(text: str, output_path: str) -> None:
    """Write reference text to a file.
    
    Args:
        text: Text content to write
        output_path: Path to output file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")


def check_model_cached(model_name: str) -> bool:
    """Check if MFA model is cached locally.
    
    Args:
        model_name: Name of the MFA model (e.g., "english_us_arpa")
        
    Returns:
        True if model is cached, False otherwise
    """
    # MFA default cache location: ~/.local/share/mfa/models/
    home = Path.home()
    model_path = home / ".local" / "share" / "mfa" / "models" / model_name
    return model_path.exists()


def get_mfa_model_path(model_name: str) -> Optional[str]:
    """Get the path to a cached MFA model.
    
    Args:
        model_name: Name of the MFA model
        
    Returns:
        Path to model if cached, None otherwise
    """
    if check_model_cached(model_name):
        home = Path.home()
        model_path = home / ".local" / "share" / "mfa" / "models" / model_name
        return str(model_path)
    return None
