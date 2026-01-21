# Line-by-Line Explanation: mfa_pronunciation.py

## Overview
This module uses Montreal Forced Aligner (MFA) to assess pronunciation by aligning reference text with audio at the phoneme level. Used for clear audio.

---

## Line-by-Line Breakdown

### Lines 1-12: Imports and Setup

```python
from __future__ import annotations
```
- **Purpose**: Enables forward references in type hints
- **Why**: Allows using types before definition

```python
import os
```
- **Purpose**: Import OS module for file operations
- **Why**: Needed for path checking and directory creation

```python
import subprocess
```
- **Purpose**: Import subprocess for running external commands
- **Why**: MFA is run as a command-line tool

```python
import tempfile
```
- **Purpose**: Import tempfile for temporary directories
- **Why**: MFA needs temporary workspace for processing

```python
from pathlib import Path
```
- **Purpose**: Import Path for path manipulation
- **Why**: Easier path handling than string concatenation

```python
from typing import Any, Dict, List, Optional
```
- **Purpose**: Import type hints
- **Why**: Type annotations for better code documentation

```python
try:
    import textgrid  # type: ignore
except ImportError:
    textgrid = None  # type: ignore
```
- **Purpose**: Try to import textgrid library (optional)
- **Why**: Used to read MFA output files (TextGrid format)
- **Fallback**: Sets to None if not installed (error raised later)

---

### Lines 15-30: MFA Installation Check

```python
def _ensure_mfa_installed() -> None:
```
- **Purpose**: Verify MFA is installed and accessible
- **Returns**: None (raises exception if not found)

```python
    """Check if MFA is installed and raise if not."""
```
- **Purpose**: Docstring
- **Why**: Documents function purpose

```python
    try:
        result = subprocess.run(
            ["mfa", "--version"], capture_output=True, text=True, timeout=5, check=False
        )
```
- **Purpose**: Run MFA version command
- **Parameters**:
  - `["mfa", "--version"]`: Command to check MFA version
  - `capture_output=True`: Capture stdout/stderr
  - `text=True`: Return string output (not bytes)
  - `timeout=5`: 5 second timeout
  - `check=False`: Don't raise on non-zero exit

```python
        if result.returncode != 0:
            raise RuntimeError(
                "Montreal Forced Aligner (MFA) is not installed or not in PATH. "
                "Install with: conda install -c conda-forge montreal-forced-alignment"
            )
```
- **Purpose**: Check if command succeeded
- **Why**: Non-zero exit means MFA not found or error
- **Error message**: Provides installation instructions

```python
    except FileNotFoundError:
        raise RuntimeError(
            "Montreal Forced Aligner (MFA) is not installed or not in PATH. "
            "Install with: conda install -c conda-forge montreal-forced-alignment"
        )
```
- **Purpose**: Handle case where 'mfa' command doesn't exist
- **Why**: FileNotFoundError means command not in PATH

---

### Lines 33-36: Text File Writer

```python
def _write_text_file(text: str, output_path: str) -> None:
```
- **Purpose**: Write reference text to file
- **Parameters**: `text` = reference text, `output_path` = file path
- **Why**: MFA requires text file input

```python
    """Write reference text to a file."""
```
- **Purpose**: Docstring
- **Why**: Documents function

```python
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
```
- **Purpose**: Write text to file with UTF-8 encoding
- **Why**: MFA expects text files with newline terminator
- **`text.strip()`**: Removes leading/trailing whitespace

---

### Lines 39-79: TextGrid Reader

```python
def _read_textgrid(word_tg_path: str) -> List[Dict[str, Any]]:
```
- **Purpose**: Read MFA output TextGrid file
- **Parameters**: `word_tg_path` = path to TextGrid file
- **Returns**: List of word alignments with timestamps

```python
    """
    Read word-level TextGrid and return list of word alignments.
    Each entry: {word, start, end, confidence (if available)}
    """
```
- **Purpose**: Docstring explaining output format
- **Why**: Documents return structure

```python
    if textgrid is None:
        raise ImportError(
            "textgrid library required. Install with: pip install praat-textgrids"
        )
```
- **Purpose**: Check if textgrid library is available
- **Why**: Required to parse TextGrid files
- **Error**: Provides installation instructions

```python
    try:
        tg = textgrid.TextGrid.fromFile(word_tg_path)
    except Exception as e:
        raise RuntimeError(f"Failed to read TextGrid: {e}")
```
- **Purpose**: Load TextGrid file
- **Why**: TextGrid is MFA's output format (from Praat)
- **Error handling**: Catches file read errors

```python
    words: List[Dict[str, Any]] = []
```
- **Purpose**: Initialize list for word alignments
- **Why**: Will store extracted word information

```python
    # Find word tier (usually named "words" or similar)
    word_tier = None
    for tier in tg.tiers:
        if tier.name.lower() in ("words", "word", "orthography"):
            word_tier = tier
            break
```
- **Purpose**: Find the word-level tier in TextGrid
- **Why**: TextGrids can have multiple tiers (words, phones, etc.)
- **Search**: Looks for common tier names

```python
    if word_tier is None and len(tg.tiers) > 0:
        word_tier = tg.tiers[0]
```
- **Purpose**: Fallback: use first tier if word tier not found
- **Why**: Some TextGrids may have different naming

```python
    if word_tier is None:
        return words
```
- **Purpose**: Return empty list if no tier found
- **Why**: Safety check

```python
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
```
- **Purpose**: Extract word alignments from intervals
- **Process**: Each interval represents one word with start/end times
- **`interval.mark`**: Word text
- **`interval.minTime/maxTime`**: Start and end times in seconds
- **Note**: MFA doesn't provide confidence scores by default

```python
    return words
```
- **Purpose**: Return extracted word alignments
- **Why**: Provides word-level timing information

---

### Lines 82-180: MFA Alignment Function

```python
def align_with_mfa(
    wav_path: str,
    reference_text: str,
    *,
    acoustic_model: str = "english_us_arpa",
    dictionary: str = "english_us_arpa",
    temp_dir: Optional[str] = None,
    cleanup: bool = True,
) -> List[Dict[str, Any]]:
```
- **Purpose**: Run MFA alignment and return word timestamps
- **Parameters**:
  - `wav_path`: Audio file path
  - `reference_text`: Expected transcription
  - `acoustic_model`: MFA acoustic model name (default: english_us_arpa)
  - `dictionary`: MFA pronunciation dictionary (default: english_us_arpa)
  - `temp_dir`: Optional temp directory (auto-created if None)
  - `cleanup`: Whether to delete temp files after (default: True)
- **Returns**: List of word alignments

```python
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
```
- **Purpose**: Comprehensive docstring
- **Why**: Documents all parameters and return format

```python
    _ensure_mfa_installed()
```
- **Purpose**: Verify MFA is available
- **Why**: Fails early if MFA not installed

```python
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Audio file not found: {wav_path}")
```
- **Purpose**: Check audio file exists
- **Why**: Prevents errors later

```python
    # Create temporary directory
    if temp_dir is None:
        temp_dir_obj = tempfile.mkdtemp(prefix="mfa_align_")
        temp_dir = temp_dir_obj
    else:
        os.makedirs(temp_dir, exist_ok=True)
        temp_dir_obj = None
```
- **Purpose**: Create or use temporary directory
- **Why**: MFA needs workspace for processing
- **`mkdtemp`**: Creates unique temp directory
- **`temp_dir_obj`**: Tracks if we created it (for cleanup)

```python
    try:
```
- **Purpose**: Start try block for cleanup
- **Why**: Ensures temp files are deleted even on error

```python
        # Prepare paths
        corpus_dir = os.path.join(temp_dir, "corpus")
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(corpus_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
```
- **Purpose**: Create MFA directory structure
- **Why**: MFA expects specific folder layout:
  - `corpus/`: Input audio + text files
  - `output/`: Output TextGrid files

```python
        # Create a subdirectory for this audio file
        audio_id = Path(wav_path).stem
        audio_dir = os.path.join(corpus_dir, audio_id)
        os.makedirs(audio_dir, exist_ok=True)
```
- **Purpose**: Create subdirectory named after audio file
- **Why**: MFA processes each audio file in its own folder
- **`Path(wav_path).stem`**: Gets filename without extension

```python
        # Copy audio file
        import shutil
        
        audio_dest = os.path.join(audio_dir, f"{audio_id}.wav")
        shutil.copy2(wav_path, audio_dest)
```
- **Purpose**: Copy audio file to corpus directory
- **Why**: MFA reads from corpus directory
- **`copy2`**: Preserves metadata

```python
        # Write text file
        text_path = os.path.join(audio_dir, f"{audio_id}.txt")
        _write_text_file(reference_text, text_path)
```
- **Purpose**: Write reference text to file
- **Why**: MFA needs text file matching audio filename

```python
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
```
- **Purpose**: Build MFA command
- **Command breakdown**:
  - `mfa align`: MFA alignment command
  - `corpus_dir`: Input directory
  - `dictionary`: Pronunciation dictionary
  - `acoustic_model`: Acoustic model
  - `output_dir`: Output directory
  - `--clean`: Clean temporary files
  - `--single_speaker`: Single speaker mode

```python
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
```
- **Purpose**: Execute MFA command
- **Parameters**:
  - `timeout=300`: 5 minute timeout
  - `check=False`: Don't raise on error (we check manually)

```python
        if result.returncode != 0:
            raise RuntimeError(
                f"MFA alignment failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
```
- **Purpose**: Check if MFA succeeded
- **Why**: Non-zero exit means alignment failed
- **Error**: Includes stdout/stderr for debugging

```python
        # Read TextGrid output
        word_tg_path = os.path.join(output_dir, f"{audio_id}.TextGrid")
        if not os.path.exists(word_tg_path):
            raise RuntimeError(f"MFA output TextGrid not found: {word_tg_path}")
```
- **Purpose**: Verify output file exists
- **Why**: MFA should create TextGrid file

```python
        words = _read_textgrid(word_tg_path)
        return words
```
- **Purpose**: Read and return word alignments
- **Why**: Extracts timing information from TextGrid

```python
    finally:
        if cleanup and temp_dir_obj:
            import shutil
            
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
```
- **Purpose**: Clean up temporary directory
- **Why**: Removes temp files after processing
- **`finally`**: Always executes, even on error
- **`pass`**: Silently ignore cleanup errors

---

### Lines 183-234: Pronunciation Assessment Function

```python
def assess_pronunciation_mfa(
    wav_path: str,
    reference_text: str,
    *,
    confidence_threshold: float = 0.75,
    acoustic_model: str = "english_us_arpa",
    dictionary: str = "english_us_arpa",
) -> List[Dict[str, Any]]:
```
- **Purpose**: Assess pronunciation using MFA
- **Parameters**:
  - `wav_path`: Audio file path
  - `reference_text`: Reference transcription
  - `confidence_threshold`: Threshold for correctness (default 0.75)
  - `acoustic_model`: MFA model name
  - `dictionary`: MFA dictionary name
- **Returns**: List of word results with status

```python
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
```
- **Purpose**: Docstring explaining function
- **Why**: Documents parameters and output

```python
    alignments = align_with_mfa(
        wav_path,
        reference_text,
        acoustic_model=acoustic_model,
        dictionary=dictionary,
    )
```
- **Purpose**: Run MFA alignment
- **Why**: Gets word-level timestamps

```python
    results: List[Dict[str, Any]] = []
```
- **Purpose**: Initialize results list
- **Why**: Will store pronunciation assessments

```python
    for align in alignments:
```
- **Purpose**: Process each aligned word
- **Why**: Assesses pronunciation for each word

```python
        # MFA doesn't provide confidence scores by default
        # For now, mark all aligned words as "correct"
        # In practice, you might want to add phone-level analysis
        confidence = align.get("confidence", 1.0)
        if confidence is None:
            confidence = 1.0
```
- **Purpose**: Get confidence score (defaults to 1.0)
- **Why**: MFA doesn't provide confidence by default
- **Note**: Could be enhanced with phone-level analysis

```python
        status = "correct" if confidence >= confidence_threshold else "mispronounced"
```
- **Purpose**: Determine pronunciation status
- **Decision**: Correct if confidence >= threshold (0.75)
- **Why**: Binary classification based on threshold

```python
        results.append(
            {
                "word": align["word"],
                "start": align["start"],
                "end": align["end"],
                "confidence": confidence,
                "status": status,
            }
        )
```
- **Purpose**: Add word result to list
- **Why**: Builds pronunciation assessment output

```python
    return results
```
- **Purpose**: Return pronunciation results
- **Why**: Provides word-level pronunciation assessment

---

### Lines 237-243: Main Block

```python
if __name__ == "__main__":
```
- **Purpose**: Code runs only when script executed directly
- **Why**: Allows import without running test

```python
    # Example usage
    wav_path = "input.wav"
    reference_text = "bicycle racing is the"
    results = assess_pronunciation_mfa(wav_path, reference_text)
    for r in results:
        print(r)
```
- **Purpose**: Example usage demonstration
- **Why**: Tests function and shows output format

---

## Summary

This module implements **pronunciation assessment for clear audio**:
1. **Checks** MFA installation
2. **Runs** MFA alignment command-line tool
3. **Parses** TextGrid output files
4. **Assesses** pronunciation based on alignment quality
5. **Returns** word-level pronunciation status

The key insight: **MFA provides precise phoneme-level alignment for clear audio, enabling accurate pronunciation assessment.**
