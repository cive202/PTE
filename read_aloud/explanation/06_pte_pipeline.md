# Line-by-Line Explanation: pte_pipeline.py

## Overview
This module orchestrates the entire PTE (Pronunciation Test Engine) pipeline, coordinating all components to produce a unified word-level assessment report.

---

## Line-by-Line Breakdown

### Lines 1-10: Imports

```python
from __future__ import annotations
```
- **Purpose**: Enables forward references in type hints
- **Why**: Allows using types before definition

```python
from typing import Any, Dict, List, Optional
```
- **Purpose**: Import type hints
- **Why**: Type annotations for documentation

```python
from audio_quality import is_audio_clear
from mfa_pronunciation import assess_pronunciation_mfa
from report_generator import generate_final_report
from voice2text import voice2text
from wavlm_pronunciation import assess_pronunciation_wavlm
from word_level_matcher import word_level_matcher
```
- **Purpose**: Import all pipeline components
- **Why**: Each module handles one part of the pipeline:
  - `audio_quality`: Clarity detection
  - `mfa_pronunciation`: MFA pronunciation assessment
  - `report_generator`: Report generation
  - `voice2text`: ASR transcription
  - `wavlm_pronunciation`: WavLM fallback
  - `word_level_matcher`: Content alignment

---

### Lines 13-117: Main Pipeline Function

```python
def assess_pte(
    wav_path: str,
    reference_text: str,
    *,
    asr_confidence_threshold: float = 0.75,
    silence_ratio_threshold: float = 0.35,
    pronunciation_threshold_clear: float = 0.75,
    pronunciation_threshold_noisy: float = 0.6,
    mfa_acoustic_model: str = "english_us_arpa",
    mfa_dictionary: str = "english_us_arpa",
) -> Dict[str, Any]:
```
- **Purpose**: Main PTE pipeline orchestrator
- **Parameters**:
  - `wav_path`: Audio file path
  - `reference_text`: Expected transcription
  - `asr_confidence_threshold`: ASR confidence threshold (default 0.75)
  - `silence_ratio_threshold`: Silence ratio threshold (default 0.35)
  - `pronunciation_threshold_clear`: Pronunciation threshold for clear audio (default 0.75)
  - `pronunciation_threshold_noisy`: Pronunciation threshold for noisy audio (default 0.6)
  - `mfa_acoustic_model`: MFA model name
  - `mfa_dictionary`: MFA dictionary name
- **Returns**: Complete assessment report

```python
    """
    Main PTE (Pronunciation Test Engine) pipeline orchestrator.
    
    Pipeline flow:
    1. Run ASR to get spoken words + timestamps
    2. Tokenize and align reference text with ASR output (content matching)
    3. Detect audio clarity (ASR confidence + silence ratio)
    4. Route to MFA (clear audio) or WavLM-CTC (noisy audio) for pronunciation
    5. Generate unified word-level report combining content and pronunciation
    
    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription text
        asr_confidence_threshold: Threshold for ASR confidence (default: 0.75)
        silence_ratio_threshold: Threshold for silence ratio (default: 0.35)
        pronunciation_threshold_clear: Pronunciation threshold for clear audio/MFA (default: 0.75)
        pronunciation_threshold_noisy: Pronunciation threshold for noisy audio/WavLM (default: 0.6)
        mfa_acoustic_model: MFA acoustic model name
        mfa_dictionary: MFA dictionary name
    
    Returns:
        Dict with:
            - "words": List of {word, status, start, end, confidence}
            - "summary": Statistics dict
            - "audio_clear": Whether audio was classified as clear
            - "pronunciation_method": "mfa" or "wavlm"
    """
```
- **Purpose**: Comprehensive docstring
- **Why**: Documents entire pipeline flow and parameters

```python
    # Step 1: Run ASR
    asr_result = voice2text(wav_path)
    asr_words = asr_result.get("word_timestamps", [])
```
- **Purpose**: Run Automatic Speech Recognition
- **Why**: Gets what words were actually spoken with timestamps
- **Step 1**: ASR transcription

```python
    
    # Calculate average ASR confidence if available
    # Note: Parakeet may not provide confidence scores directly
    # For now, we'll estimate based on whether words were detected
    asr_confidence = None
    if asr_words:
        # Simple heuristic: if we got words, assume reasonable confidence
        # In practice, extract actual confidence from ASR output if available
        asr_confidence = 0.8  # Placeholder - should be extracted from ASR
```
- **Purpose**: Estimate ASR confidence
- **Why**: Needed for audio clarity detection
- **Note**: Placeholder - should extract actual confidence from ASR

```python
    # Step 2: Word-level matching (content alignment)
    content_results = word_level_matcher(wav_path, reference_text)
```
- **Purpose**: Align reference text with ASR output
- **Why**: Detects content errors (missed, repeated, substituted words)
- **Step 2**: Content alignment

```python
    # Step 3: Detect audio clarity
    audio_clear, quality_metrics = is_audio_clear(
        wav_path,
        asr_confidence=asr_confidence,
        silence_ratio_threshold=silence_ratio_threshold,
        asr_confidence_threshold=asr_confidence_threshold,
    )
```
- **Purpose**: Determine if audio is clear enough for MFA
- **Decision**: Based on ASR confidence and silence ratio
- **Step 3**: Audio clarity gate
- **Returns**: Boolean (clear or not) and quality metrics

```python
    # Step 4: Pronunciation assessment based on audio clarity
    if audio_clear:
```
- **Purpose**: Route to appropriate pronunciation method
- **Why**: Clear audio uses MFA, noisy uses WavLM

```python
        # Use MFA for clear audio
        try:
            pronunciation_results = assess_pronunciation_mfa(
                wav_path,
                reference_text,
                confidence_threshold=pronunciation_threshold_clear,
                acoustic_model=mfa_acoustic_model,
                dictionary=mfa_dictionary,
            )
            pronunciation_method = "mfa"
```
- **Purpose**: Run MFA pronunciation assessment
- **Why**: MFA is accurate for clear audio
- **Threshold**: 0.75 (stricter for clear audio)
- **Step 4a**: MFA pronunciation assessment

```python
        except Exception as e:
            # Fallback to WavLM if MFA fails
            print(f"Warning: MFA failed ({e}), falling back to WavLM")
            pronunciation_results = assess_pronunciation_wavlm(
                wav_path,
                reference_text,
                confidence_threshold=pronunciation_threshold_noisy,
            )
            pronunciation_method = "wavlm_fallback"
```
- **Purpose**: Fallback to WavLM if MFA fails
- **Why**: MFA may fail (installation issues, model errors)
- **Error handling**: Catches exceptions and falls back gracefully

```python
    else:
        # Use WavLM-CTC for noisy audio
        pronunciation_results = assess_pronunciation_wavlm(
            wav_path,
            reference_text,
            confidence_threshold=pronunciation_threshold_noisy,
        )
        pronunciation_method = "wavlm"
```
- **Purpose**: Use WavLM for noisy audio
- **Why**: WavLM is more robust to noise than MFA
- **Threshold**: 0.6 (looser for noisy audio)
- **Step 4b**: WavLM pronunciation assessment

```python
    # Step 5: Generate unified report
    final_report = generate_final_report(content_results, pronunciation_results)
```
- **Purpose**: Merge content and pronunciation results
- **Why**: Creates unified word-level report
- **Step 5**: Report generation

```python
    # Add metadata
    final_report["audio_clear"] = audio_clear
    final_report["pronunciation_method"] = pronunciation_method
```
- **Purpose**: Add pipeline metadata
- **Why**: Tracks which method was used and audio quality

```python
    final_report["quality_metrics"] = {
        "silence_ratio": quality_metrics.silence_ratio,
        "rms_mean": quality_metrics.rms_mean,
        "duration_s": quality_metrics.duration_s,
    }
```
- **Purpose**: Add audio quality metrics
- **Why**: Provides diagnostic information

```python
    return final_report
```
- **Purpose**: Return complete assessment report
- **Why**: Provides final output with all information

---

### Lines 120-133: Simplified Interface

```python
def assess_pte_simple(
    wav_path: str, reference_text: str
) -> Dict[str, Any]:
```
- **Purpose**: Simplified interface with default parameters
- **Parameters**: Only audio path and reference text
- **Returns**: Same report format as `assess_pte`

```python
    """
    Simplified interface with default parameters.
    
    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription text
    
    Returns:
        Unified report dict (same format as assess_pte)
    """
```
- **Purpose**: Docstring
- **Why**: Documents simplified interface

```python
    return assess_pte(wav_path, reference_text)
```
- **Purpose**: Call main function with defaults
- **Why**: Provides easy-to-use interface

---

### Lines 136-164: Main Block

```python
if __name__ == "__main__":
```
- **Purpose**: Code runs only when script executed directly
- **Why**: Allows import without running test

```python
    # Example usage
    wav_path = "input.wav"
    reference_text = "bicycle racing is the"
```
- **Purpose**: Example inputs
- **Why**: Demonstrates usage

```python
    print("Running PTE pipeline...")
    result = assess_pte_simple(wav_path, reference_text)
```
- **Purpose**: Run pipeline
- **Why**: Tests complete system

```python
    print("\n=== Summary ===")
    summary = result["summary"]
    print(f"Total words: {summary['total_words']}")
    print(f"Correct: {summary['correct']}")
    print(f"Mispronounced: {summary['mispronounced']}")
    print(f"Missed: {summary['missed']}")
    print(f"Repeated: {summary['repeated']}")
    print(f"Substituted: {summary['substituted']}")
    print(f"Accuracy: {summary['accuracy']:.1f}%")
    print(f"Average confidence: {summary['average_confidence']:.2f}")
```
- **Purpose**: Print summary statistics
- **Why**: Shows overall assessment metrics

```python
    print(f"\nAudio clear: {result['audio_clear']}")
    print(f"Pronunciation method: {result['pronunciation_method']}")
```
- **Purpose**: Print pipeline metadata
- **Why**: Shows which method was used

```python
    print("\n=== Word-level Results ===")
    for word_result in result["words"][:10]:  # Show first 10
        print(
            f"{word_result['word']}: {word_result['status']} "
            f"(start={word_result.get('start')}, end={word_result.get('end')}, "
            f"confidence={word_result.get('confidence', 0.0):.2f})"
        )
```
- **Purpose**: Print word-level results
- **Why**: Shows detailed assessment for each word
- **Limit**: First 10 words (to avoid long output)

---

## Pipeline Flow Summary

The complete pipeline follows these steps:

1. **ASR Transcription** (`voice2text`)
   - Gets spoken words + timestamps
   - Extracts ASR confidence (if available)

2. **Content Alignment** (`word_level_matcher`)
   - Aligns reference text with ASR output
   - Detects missed, repeated, substituted words

3. **Audio Clarity Detection** (`is_audio_clear`)
   - Analyzes ASR confidence + silence ratio
   - Decides: clear → MFA, noisy → WavLM

4. **Pronunciation Assessment**
   - **If clear**: MFA (Montreal Forced Aligner)
   - **If noisy**: WavLM-CTC (neural network fallback)
   - **If MFA fails**: Fallback to WavLM

5. **Report Generation** (`generate_final_report`)
   - Merges content + pronunciation results
   - Applies decision rules
   - Calculates statistics
   - Returns unified report

---

## Key Design Principles

1. **Content errors come from sequence alignment** (word_level_matcher)
2. **Pronunciation errors come from forced alignment** (MFA/WavLM)
3. **Never mix content and pronunciation detection**
4. **Audio clarity determines pronunciation method**, not content detection
5. **Content errors take precedence** over pronunciation assessment

---

## Summary

This module implements the **complete PTE pipeline orchestrator**:
1. **Coordinates** all components in correct order
2. **Routes** to appropriate pronunciation method based on audio quality
3. **Handles** errors gracefully (MFA fallback)
4. **Generates** unified report with metadata
5. **Provides** simple interface for easy usage

The key insight: **The pipeline separates content accuracy (what was said) from pronunciation accuracy (how it was said), routing pronunciation assessment based on audio quality.**
