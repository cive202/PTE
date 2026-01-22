"""MFA CLI command execution."""
from __future__ import annotations

import subprocess
from typing import Literal


def run_mfa_align(
    corpus_dir: str,
    dictionary: str,
    acoustic_model: str,
    output_dir: str,
    *,
    output_format: Literal["textgrid", "json"] = "textgrid",
) -> None:
    """Run MFA align command.
    
    Args:
        corpus_dir: Directory containing audio and text files
        dictionary: MFA dictionary name (e.g., "english_us_arpa")
        acoustic_model: MFA acoustic model name (e.g., "english_us_arpa")
        output_dir: Directory for MFA output
        output_format: Output format - "textgrid" (default) or "json" (for phone-level)
        
    Raises:
        RuntimeError: If MFA alignment fails
    """
    cmd = [
        "mfa",
        "align",
        corpus_dir,
        dictionary,
        acoustic_model,
        output_dir,
        "--clean",
        "--single_speaker",
    ]
    
    # Add JSON output format if requested (enables phone-level analysis)
    if output_format == "json":
        cmd.extend(["--output_format", "json"])
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"MFA alignment failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
