# Line-by-Line Explanation: wavlm_pronunciation.py

## Overview
This module uses WavLM-CTC (Connectionist Temporal Classification) as a fallback for pronunciation assessment when audio quality is poor. WavLM is more robust to noise than MFA.

---

## Line-by-Line Breakdown

### Lines 1-15: Imports and Error Handling

```python
from __future__ import annotations
```
- **Purpose**: Enables forward references in type hints
- **Why**: Allows using types before definition

```python
import re
```
- **Purpose**: Import regex for text processing
- **Why**: Needed for word extraction and pattern matching

```python
from typing import Any, Dict, List, Optional
```
- **Purpose**: Import type hints
- **Why**: Type annotations for documentation

```python
try:
    import torch
    from transformers import WavLMForCTC, Wav2Vec2Processor  # type: ignore
    import soundfile as sf  # type: ignore
    import numpy as np
except ImportError as e:
    raise ImportError(
        f"Required libraries not installed: {e}\n"
        "Install with: pip install torch transformers soundfile numpy"
    )
```
- **Purpose**: Import required libraries with error handling
- **Libraries**:
  - `torch`: PyTorch for neural networks
  - `WavLMForCTC`: WavLM model with CTC head
  - `Wav2Vec2Processor`: Audio processor for WavLM
  - `soundfile`: Audio file reading
  - `numpy`: Numerical operations
- **Error**: Provides installation instructions if missing

---

### Lines 18-25: Constants

```python
# Phoneme mapping for English (simplified - you may want to use CMU dict)
PHONEME_MAP: Dict[str, List[str]] = {
    # Add common word mappings here
    # Example: "bicycle": ["B", "AY", "S", "IH", "K", "AH", "L"]
}
```
- **Purpose**: Dictionary mapping words to phoneme sequences
- **Why**: Converts text to expected phonemes
- **Note**: Currently empty - should use CMU dictionary in practice

```python
# CTC blank token
CTC_BLANK = "<blank>"
```
- **Purpose**: Define CTC blank token symbol
- **Why**: CTC uses blank tokens for alignment
- **Note**: Not used in current implementation but documented

---

### Lines 28-34: Model Loading

```python
def _load_wavlm_model() -> tuple[Any, Any]:
```
- **Purpose**: Load WavLM model and processor
- **Returns**: (model, processor) tuple
- **Why**: Model loading is expensive, can be cached

```python
    """Load WavLM model and processor."""
```
- **Purpose**: Docstring
- **Why**: Documents function

```python
    model_name = "microsoft/wavlm-base-plus"
```
- **Purpose**: Specify WavLM model name
- **Why**: HuggingFace model identifier

```python
    processor = Wav2Vec2Processor.from_pretrained(model_name)
```
- **Purpose**: Load audio processor
- **Why**: Preprocesses audio for model input

```python
    model = WavLMForCTC.from_pretrained(model_name)
```
- **Purpose**: Load WavLM model with CTC head
- **Why**: CTC enables sequence-to-sequence alignment

```python
    model.eval()
```
- **Purpose**: Set model to evaluation mode
- **Why**: Disables dropout and batch normalization updates

```python
    return model, processor
```
- **Purpose**: Return loaded model and processor
- **Why**: Provides ready-to-use model

---

### Lines 37-42: Audio Loading

```python
def _load_audio(wav_path: str) -> tuple[np.ndarray, int]:
```
- **Purpose**: Load audio file
- **Parameters**: `wav_path` = audio file path
- **Returns**: (waveform array, sample_rate)

```python
    """Load audio file and return (waveform, sample_rate)."""
```
- **Purpose**: Docstring
- **Why**: Documents function

```python
    waveform, sample_rate = sf.read(wav_path)
```
- **Purpose**: Read audio file using soundfile
- **Why**: soundfile handles various audio formats

```python
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=1)
```
- **Purpose**: Convert stereo to mono
- **Why**: Model expects mono audio
- **Method**: Average across channels

```python
    return waveform.astype(np.float32), int(sample_rate)
```
- **Purpose**: Return waveform and sample rate
- **Why**: Ensures correct data types

---

### Lines 45-63: Text to Phonemes Conversion

```python
def _text_to_phonemes(text: str, phoneme_dict: Optional[Dict[str, List[str]]] = None) -> List[str]:
```
- **Purpose**: Convert text to phoneme sequence
- **Parameters**: `text` = input text, `phoneme_dict` = optional dictionary
- **Returns**: List of phoneme symbols

```python
    """
    Convert text to phoneme sequence.
    This is a simplified version - in practice, use a proper pronunciation dictionary.
    """
```
- **Purpose**: Docstring with note about simplification
- **Why**: Current implementation is basic

```python
    if phoneme_dict is None:
        phoneme_dict = PHONEME_MAP
```
- **Purpose**: Use default phoneme map if none provided
- **Why**: Allows custom dictionaries

```python
    words = re.findall(r"\b\w+\b", text.lower())
```
- **Purpose**: Extract words from text
- **Regex**: `\b\w+\b` matches word boundaries
- **Why**: Processes word by word

```python
    phonemes: List[str] = []
```
- **Purpose**: Initialize phoneme list
- **Why**: Will store phoneme sequence

```python
    for word in words:
        if word in phoneme_dict:
            phonemes.extend(phoneme_dict[word])
        else:
            # Fallback: map each letter (very rough approximation)
            # In practice, use CMU dict or similar
            phonemes.extend(list(word))
```
- **Purpose**: Convert each word to phonemes
- **Process**: Look up in dictionary, or fallback to letter mapping
- **Why**: Handles unknown words (simplified)

```python
    return phonemes
```
- **Purpose**: Return phoneme sequence
- **Why**: Provides expected phonemes for comparison

---

### Lines 66-80: CTC Decoding

```python
def _decode_ctc_phonemes(
    logits: torch.Tensor, processor: Any, vocab_size: int
) -> List[str]:
```
- **Purpose**: Decode CTC logits to phoneme sequence
- **Parameters**: `logits` = model output, `processor` = audio processor, `vocab_size` = vocabulary size
- **Returns**: List of phoneme IDs (as strings)

```python
    """Decode CTC logits to phoneme sequence."""
```
- **Purpose**: Docstring
- **Why**: Documents function

```python
    predicted_ids = torch.argmax(logits, dim=-1)
```
- **Purpose**: Get predicted token IDs (greedy decoding)
- **Why**: CTC outputs probability distribution, argmax gets most likely token

```python
    # Convert to list and remove CTC blanks and repeated tokens
    pred_sequence = predicted_ids[0].cpu().numpy().tolist()
```
- **Purpose**: Convert tensor to Python list
- **Process**: Move to CPU, convert to numpy, then list
- **Why**: CTC decoding needs Python list

```python
    # Simple CTC decoding (remove blanks and consecutive duplicates)
    decoded: List[str] = []
    prev_id = None
    for token_id in pred_sequence:
        if token_id != prev_id and token_id < vocab_size and token_id != processor.tokenizer.pad_token_id:
            decoded.append(str(token_id))
        prev_id = token_id
```
- **Purpose**: Simple CTC decoding (remove blanks and duplicates)
- **Process**:
  - Skip if same as previous (removes duplicates)
  - Skip if invalid token ID
  - Skip padding tokens
- **Why**: CTC produces repeated tokens, need to collapse them
- **Note**: This is simplified - full CTC decoding is more complex

```python
    return decoded
```
- **Purpose**: Return decoded phoneme IDs
- **Why**: Provides detected phoneme sequence

---

### Lines 83-117: Phoneme Extraction

```python
def extract_phonemes_wavlm(
    wav_path: str, *, model: Optional[Any] = None, processor: Optional[Any] = None
) -> tuple[List[str], List[float]]:
```
- **Purpose**: Extract phonemes from audio using WavLM
- **Parameters**: `wav_path` = audio path, `model`/`processor` = optional (loaded if None)
- **Returns**: (phoneme_sequence, timestamps_per_frame)

```python
    """
    Extract phoneme sequence from audio using WavLM-CTC.
    
    Returns:
        (phoneme_sequence, timestamps_per_frame)
    """
```
- **Purpose**: Docstring
- **Why**: Documents return format

```python
    if model is None or processor is None:
        model, processor = _load_wavlm_model()
```
- **Purpose**: Load model if not provided
- **Why**: Allows model reuse (expensive to load)

```python
    waveform, sample_rate = _load_audio(wav_path)
```
- **Purpose**: Load audio file
- **Why**: Gets waveform for processing

```python
    # Process audio
    inputs = processor(
        waveform, sampling_rate=sample_rate, return_tensors="pt", padding=True
    )
```
- **Purpose**: Preprocess audio for model
- **Process**: Normalizes, converts to tensor, adds padding
- **Why**: Model expects specific input format

```python
    with torch.no_grad():
        logits = model(inputs.input_values).logits
```
- **Purpose**: Run model inference
- **`torch.no_grad()`**: Disables gradient computation (faster)
- **Why**: Inference doesn't need gradients

```python
    # Decode (simplified - actual CTC decoding is more complex)
    vocab_size = logits.shape[-1]
    phoneme_ids = _decode_ctc_phonemes(logits, processor, vocab_size)
```
- **Purpose**: Decode model output to phoneme sequence
- **Why**: Converts logits to phoneme IDs

```python
    # Estimate timestamps (rough - each frame is ~20ms)
    frame_duration = 0.02  # seconds
    timestamps = [i * frame_duration for i in range(len(phoneme_ids))]
```
- **Purpose**: Estimate timestamps for each phoneme
- **Assumption**: Each frame is 20ms (WavLM frame rate)
- **Why**: Provides temporal information

```python
    # Map token IDs back to labels (this is simplified)
    # In practice, you'd use processor.tokenizer.decode or a phoneme vocabulary
    phonemes = [f"PHON_{pid}" for pid in phoneme_ids]
```
- **Purpose**: Convert token IDs to phoneme labels
- **Note**: Simplified - uses placeholder labels
- **Why**: In practice, would use actual phoneme vocabulary

```python
    return phonemes, timestamps
```
- **Purpose**: Return phonemes and timestamps
- **Why**: Provides detected phoneme sequence

---

### Lines 120-150: Phoneme Comparison

```python
def compare_phonemes(
    expected: List[str], detected: List[str], threshold: float = 0.7
) -> float:
```
- **Purpose**: Compare expected vs detected phonemes
- **Parameters**: `expected` = reference phonemes, `detected` = detected phonemes, `threshold` = unused
- **Returns**: Similarity score (0.0 to 1.0)

```python
    """
    Compare expected vs detected phonemes and return similarity score.
    Uses simple sequence alignment.
    """
```
- **Purpose**: Docstring
- **Why**: Documents algorithm

```python
    n, m = len(expected), len(detected)
```
- **Purpose**: Get sequence lengths
- **Why**: Needed for edit distance

```python
    if n == 0 and m == 0:
        return 1.0
```
- **Purpose**: Handle empty sequences
- **Why**: Both empty = perfect match

```python
    if n == 0 or m == 0:
        return 0.0
```
- **Purpose**: Handle one empty sequence
- **Why**: No match possible

```python
    # Simple Levenshtein-based similarity
    dp = [[0] * (m + 1) for _ in range(n + 1)]
```
- **Purpose**: Initialize edit distance table
- **Why**: Dynamic programming for sequence alignment

```python
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
```
- **Purpose**: Initialize base cases
- **Why**: Aligning to empty sequence requires deletions/insertions

```python
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if expected[i - 1] == detected[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost
            )
```
- **Purpose**: Fill edit distance table
- **Operations**: Deletion, insertion, substitution/match
- **Why**: Computes minimum edit distance

```python
    edit_distance = dp[n][m]
    max_len = max(n, m)
    similarity = 1.0 - (edit_distance / max_len) if max_len > 0 else 0.0
```
- **Purpose**: Convert edit distance to similarity score
- **Formula**: similarity = 1 - (edit_distance / max_length)
- **Why**: Normalizes to 0-1 range

```python
    return similarity
```
- **Purpose**: Return similarity score
- **Why**: Provides phoneme match quality

---

### Lines 153-217: Pronunciation Assessment

```python
def assess_pronunciation_wavlm(
    wav_path: str,
    reference_text: str,
    *,
    confidence_threshold: float = 0.6,  # Looser threshold for noisy audio
    phoneme_dict: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
```
- **Purpose**: Assess pronunciation using WavLM (fallback for noisy audio)
- **Parameters**:
  - `wav_path`: Audio file path
  - `reference_text`: Reference transcription
  - `confidence_threshold`: Threshold for correctness (default 0.6, looser than MFA)
  - `phoneme_dict`: Optional pronunciation dictionary
- **Returns**: List of word results with status

```python
    """
    Use WavLM-CTC to assess pronunciation (fallback for noisy audio).
    
    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription
        confidence_threshold: Threshold for pronunciation correctness (lower for fallback)
        phoneme_dict: Optional pronunciation dictionary
    
    Returns:
        List of dicts: {word, start, end, confidence, status}
        status: "correct" or "mispronounced"
    """
```
- **Purpose**: Docstring
- **Why**: Documents function and parameters

```python
    model, processor = _load_wavlm_model()
```
- **Purpose**: Load WavLM model
- **Why**: Gets model for phoneme extraction

```python
    # Extract phonemes from audio
    detected_phonemes, phoneme_timestamps = extract_phonemes_wavlm(
        wav_path, model=model, processor=processor
    )
```
- **Purpose**: Extract phonemes from audio
- **Why**: Gets what phonemes were detected

```python
    # Get expected phonemes from reference text
    expected_phonemes = _text_to_phonemes(reference_text, phoneme_dict)
```
- **Purpose**: Convert reference text to expected phonemes
- **Why**: Gets what phonemes should be present

```python
    # Simple word-level assessment (this is simplified)
    # In practice, you'd align phonemes to words and assess per word
    words = re.findall(r"\b\w+\b", reference_text.lower())
    results: List[Dict[str, Any]] = []
```
- **Purpose**: Extract words and initialize results
- **Note**: Current implementation is simplified
- **Why**: Should align phonemes to words for better accuracy

```python
    # Rough word-level timing (divide audio duration by word count)
    if phoneme_timestamps:
        total_duration = phoneme_timestamps[-1] if phoneme_timestamps else 1.0
    else:
        total_duration = 1.0
```
- **Purpose**: Estimate total audio duration
- **Why**: Needed for word-level timing

```python
    word_duration = total_duration / len(words) if words else 1.0
```
- **Purpose**: Estimate duration per word
- **Assumption**: Equal duration per word (simplified)
- **Why**: Provides rough word boundaries

```python
    # Overall phoneme similarity
    overall_similarity = compare_phonemes(expected_phonemes, detected_phonemes)
```
- **Purpose**: Compare overall phoneme sequences
- **Why**: Gets pronunciation quality score

```python
    for i, word in enumerate(words):
        # Use overall similarity as proxy (in practice, align phonemes to words)
        confidence = overall_similarity
        status = "correct" if confidence >= confidence_threshold else "mispronounced"
```
- **Purpose**: Assess each word
- **Process**: Uses overall similarity for all words (simplified)
- **Why**: Should align phonemes to words individually

```python
        start_time = i * word_duration
        end_time = (i + 1) * word_duration
```
- **Purpose**: Calculate word boundaries
- **Why**: Provides temporal information

```python
        results.append(
            {
                "word": word,
                "start": start_time,
                "end": end_time,
                "confidence": confidence,
                "status": status,
            }
        )
```
- **Purpose**: Add word result
- **Why**: Builds pronunciation assessment

```python
    return results
```
- **Purpose**: Return pronunciation results
- **Why**: Provides word-level assessment

---

### Lines 220-226: Main Block

```python
if __name__ == "__main__":
```
- **Purpose**: Code runs only when script executed directly
- **Why**: Allows import without running test

```python
    # Example usage
    wav_path = "input.wav"
    reference_text = "bicycle racing is the"
    results = assess_pronunciation_wavlm(wav_path, reference_text)
    for r in results:
        print(r)
```
- **Purpose**: Example usage
- **Why**: Tests function and shows output

---

## Summary

This module implements **pronunciation assessment for noisy audio**:
1. **Loads** WavLM model with CTC head
2. **Extracts** phonemes from audio using neural network
3. **Converts** reference text to expected phonemes
4. **Compares** expected vs detected phonemes
5. **Assesses** pronunciation with looser thresholds (for noisy audio)

The key insight: **WavLM-CTC is more robust to noise than MFA, making it suitable as a fallback for poor audio quality.**
