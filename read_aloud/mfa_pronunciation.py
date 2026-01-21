from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import textgrid  # type: ignore
except ImportError:
    textgrid = None  # type: ignore


def _ensure_mfa_installed() -> None:
    """Check if MFA is installed and raise if not."""
    try:
        result = subprocess.run(
            ["mfa", "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Montreal Forced Aligner (MFA) is not installed or not in PATH. "
                "Install with: conda install -c conda-forge montreal-forced-alignment"
            )
    except FileNotFoundError:
        raise RuntimeError(
            "Montreal Forced Aligner (MFA) is not installed or not in PATH. "
            "Install with: conda install -c conda-forge montreal-forced-alignment"
        )


def _write_text_file(text: str, output_path: str) -> None:
    """Write reference text to a file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")


def _read_textgrid(word_tg_path: str) -> List[Dict[str, Any]]:
    """
    Read word-level TextGrid and return list of word alignments.
    Each entry: {word, start, end, confidence (if available)}
    """
    if textgrid is None:
        raise ImportError(
            "textgrid library required. Install with: pip install praat-textgrids"
        )

    try:
        tg = textgrid.TextGrid.fromFile(word_tg_path)
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
                    "confidence": None,  # MFA doesn't provide confidence by default
                }
            )

    return words


def align_with_mfa(
    wav_path: str,
    reference_text: str,
    *,
    acoustic_model: str = "english_us_arpa",
    dictionary: str = "english_us_arpa",
    temp_dir: Optional[str] = None,
    cleanup: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run Montreal Forced Aligner to get word-level alignments.

    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription text
        acoustic_model: MFA acoustic model name (default: english_us_arpa)
        dictionary: MFA dictionary name (default: english_us_arpa)
        temp_dir: Temporary directory for intermediate files (auto-created if None)
        cleanup: Whether to clean up temporary files

    Returns:
        List of dicts: {word, start, end, confidence}
    """
    _ensure_mfa_installed()

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
        import shutil

        audio_dest = os.path.join(audio_dir, f"{audio_id}.wav")
        shutil.copy2(wav_path, audio_dest)

        # Write text file
        text_path = os.path.join(audio_dir, f"{audio_id}.txt")
        _write_text_file(reference_text, text_path)

        # Run MFA align
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

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"MFA alignment failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        # Read TextGrid output
        word_tg_path = os.path.join(output_dir, f"{audio_id}.TextGrid")
        if not os.path.exists(word_tg_path):
            raise RuntimeError(f"MFA output TextGrid not found: {word_tg_path}")

        words = _read_textgrid(word_tg_path)
        return words

    finally:
        if cleanup and temp_dir_obj:
            import shutil

            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def assess_pronunciation_mfa(
    wav_path: str,
    reference_text: str,
    *,
    confidence_threshold: float = 0.75,
    acoustic_model: str = "english_us_arpa",
    dictionary: str = "english_us_arpa",
) -> List[Dict[str, Any]]:
    """
    Use MFA to assess pronunciation and return word-level results.

    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription
        confidence_threshold: Threshold for pronunciation correctness (MFA doesn't provide
                             confidence by default, so this is a placeholder)
        acoustic_model: MFA acoustic model name
        dictionary: MFA dictionary name

    Returns:
        List of dicts: {word, start, end, confidence, status}
        status: "correct" or "mispronounced" (based on threshold)
    """
    alignments = align_with_mfa(
        wav_path,
        reference_text,
        acoustic_model=acoustic_model,
        dictionary=dictionary,
    )

    results: List[Dict[str, Any]] = []
    for align in alignments:
        # MFA doesn't provide confidence scores by default
        # For now, mark all aligned words as "correct"
        # In practice, you might want to add phone-level analysis
        confidence = align.get("confidence", 1.0)
        if confidence is None:
            confidence = 1.0

        status = "correct" if confidence >= confidence_threshold else "mispronounced"

        results.append(
            {
                "word": align["word"],
                "start": align["start"],
                "end": align["end"],
                "confidence": confidence,
                "status": status,
            }
        )

    return results


if __name__ == "__main__":
    # Example usage
    wav_path = "input.wav"
    reference_text = "bicycle racing is the"
    results = assess_pronunciation_mfa(wav_path, reference_text)
    for r in results:
        print(r)
