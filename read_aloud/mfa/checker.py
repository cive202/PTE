"""MFA installation verification."""
from __future__ import annotations

import subprocess


def ensure_mfa_installed() -> None:
    """Check if MFA is installed and raise if not.
    
    Raises:
        RuntimeError: If MFA is not installed or not in PATH.
    """
    try:
        result = subprocess.run(
            ["mfa", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Montreal Forced Aligner (MFA) is not installed or not in PATH. "
                "Install with: conda install -c conda-forge montreal-forced-aligner"
            )
    except FileNotFoundError:
        raise RuntimeError(
            "Montreal Forced Aligner (MFA) is not installed or not in PATH. "
            "Install with: conda install -c conda-forge montreal-forced-aligner"
        )
