"""High-level MFA alignment orchestration."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .checker import ensure_mfa_installed
from .phone_reader import read_phone_json, read_phone_textgrid
from .runner import run_mfa_align
from .textgrid_reader import read_word_textgrid
from .utils import write_text_file


def align_with_mfa(
    wav_path: str,
    reference_text: str,
    *,
    acoustic_model: str = "english_us_arpa",
    dictionary: str = "english_us_arpa",
    temp_dir: Optional[str] = None,
    cleanup: bool = True,
    include_phones: bool = True,
) -> Dict[str, Any]:
    """Run Montreal Forced Aligner to get word-level and optionally phone-level alignments.
    
    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription text
        acoustic_model: MFA acoustic model name (default: english_us_arpa)
        dictionary: MFA dictionary name (default: english_us_arpa)
        temp_dir: Temporary directory for intermediate files (auto-created if None)
        cleanup: Whether to clean up temporary files
        include_phones: Whether to extract phone-level alignments (default: True)
        
    Returns:
        Dict with:
            - "words": List of {word, start, end, status: "aligned", confidence: None}
            - "phones": List of {label, start, end, duration} (if include_phones=True)
    """
    ensure_mfa_installed()

    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    # Create temporary directory
    if temp_dir is None:
        temp_dir_obj = tempfile.mkdtemp(prefix="mfa_align_")
        temp_dir = temp_dir_obj
    else:
        os.makedirs(temp_dir, exist_ok=True)
        temp_dir_obj = None

    try:
        # Prepare paths
        corpus_dir = os.path.join(temp_dir, "corpus")
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(corpus_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # Create a subdirectory for this audio file
        audio_id = Path(wav_path).stem
        audio_dir = os.path.join(corpus_dir, audio_id)
        os.makedirs(audio_dir, exist_ok=True)

        # Copy audio file
        audio_dest = os.path.join(audio_dir, f"{audio_id}.wav")
        shutil.copy2(wav_path, audio_dest)

        # Write text file
        text_path = os.path.join(audio_dir, f"{audio_id}.txt")
        write_text_file(reference_text, text_path)

        # Run MFA align with appropriate output format
        output_format = "json" if include_phones else "textgrid"
        run_mfa_align(
            corpus_dir,
            dictionary,
            acoustic_model,
            output_dir,
            output_format=output_format,
        )

        # Read word-level output
        word_tg_path = os.path.join(output_dir, f"{audio_id}.TextGrid")
        word_json_path = os.path.join(output_dir, f"{audio_id}.json")
        
        words: List[Dict[str, Any]] = []
        if output_format == "json" and os.path.exists(word_json_path):
            # For JSON format, we still need word-level data
            # MFA JSON may contain both words and phones - for now, fall back to TextGrid
            # if it exists, otherwise we'll need to parse JSON structure
            if os.path.exists(word_tg_path):
                words = read_word_textgrid(word_tg_path)
        elif os.path.exists(word_tg_path):
            words = read_word_textgrid(word_tg_path)
        
        if not words:
            raise RuntimeError(
                f"MFA output not found. Checked: {word_tg_path} and {word_json_path}"
            )

        result: Dict[str, Any] = {"words": words}

        # Read phone-level output if requested
        if include_phones:
            phone_tg_path = os.path.join(output_dir, f"{audio_id}.TextGrid")
            phone_json_path = os.path.join(output_dir, f"{audio_id}.json")
            
            phones: List[Dict[str, Any]] = []
            if output_format == "json" and os.path.exists(phone_json_path):
                phones = read_phone_json(phone_json_path)
            elif os.path.exists(phone_tg_path):
                phones = read_phone_textgrid(phone_tg_path)
            
            result["phones"] = phones

        return result

    finally:
        if cleanup and temp_dir_obj:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
