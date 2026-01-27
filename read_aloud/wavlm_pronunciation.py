from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    import torch
    from transformers import WavLMForCTC, Wav2Vec2Processor  # type: ignore
    import soundfile as sf  # type: ignore
    import numpy as np
    WAVLM_AVAILABLE = True
except ImportError as e:
    WAVLM_AVAILABLE = False
    WAVLM_IMPORT_ERROR = str(e)


# Phoneme mapping for English (fallback if CMUdict unavailable)
PHONEME_MAP: Dict[str, List[str]] = {
    # Add common word mappings here as fallback
    # Example: "bicycle": ["B", "AY", "S", "IH", "K", "AH", "L"]
}

# Try to import CMUdict
try:
    from phonetics.cmudict import load_cmudict, text_to_phonemes, ensure_cmudict_available
    CMUDICT_AVAILABLE = True
except ImportError:
    CMUDICT_AVAILABLE = False
    load_cmudict = None  # type: ignore
    text_to_phonemes = None  # type: ignore
    ensure_cmudict_available = None  # type: ignore

# Cache for CMUdict
_CMUDICT_CACHE: Optional[Any] = None

# CTC blank token
CTC_BLANK = "<blank>"


def _load_wavlm_model() -> tuple[Any, Any]:
    """Load WavLM model and processor."""
    model_name = "microsoft/wavlm-base-plus"
    processor = Wav2Vec2Processor.from_pretrained(model_name)
    model = WavLMForCTC.from_pretrained(model_name)
    model.eval()
    return model, processor


def _load_audio(wav_path: str) -> tuple[np.ndarray, int]:
    """Load audio file and return (waveform, sample_rate)."""
    waveform, sample_rate = sf.read(wav_path)
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=1)
    return waveform.astype(np.float32), int(sample_rate)


def _text_to_phonemes(text: str, phoneme_dict: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """
    Convert text to phoneme sequence using CMUdict if available, otherwise fallback.
    """
    global _CMUDICT_CACHE
    
    # Try CMUdict first if available
    if CMUDICT_AVAILABLE and text_to_phonemes and ensure_cmudict_available:
        try:
            if ensure_cmudict_available():
                if _CMUDICT_CACHE is None:
                    _CMUDICT_CACHE = load_cmudict()
                return text_to_phonemes(text, _CMUDICT_CACHE)
        except Exception:
            # Fallback to old behavior
            pass
    
    # Fallback: use provided dict or default PHONEME_MAP
    if phoneme_dict is None:
        phoneme_dict = PHONEME_MAP

    words = re.findall(r"\b\w+\b", text.lower())
    phonemes: List[str] = []
    for word in words:
        if word in phoneme_dict:
            phonemes.extend(phoneme_dict[word])
        else:
            # Fallback: map each letter (very rough approximation)
            phonemes.extend(list(word))

    return phonemes


def _decode_ctc_phonemes(
    logits: torch.Tensor, processor: Any, vocab_size: int
) -> List[str]:
    """Decode CTC logits to phoneme sequence."""
    predicted_ids = torch.argmax(logits, dim=-1)
    # Convert to list and remove CTC blanks and repeated tokens
    pred_sequence = predicted_ids[0].cpu().numpy().tolist()
    # Simple CTC decoding (remove blanks and consecutive duplicates)
    decoded: List[str] = []
    prev_id = None
    for token_id in pred_sequence:
        if token_id != prev_id and token_id < vocab_size and token_id != processor.tokenizer.pad_token_id:
            decoded.append(str(token_id))
        prev_id = token_id
    return decoded


def extract_phonemes_wavlm(
    wav_path: str, *, model: Optional[Any] = None, processor: Optional[Any] = None
) -> tuple[List[str], List[float]]:
    """
    Extract phoneme sequence from audio using WavLM-CTC.

    Returns:
        (phoneme_sequence, timestamps_per_frame)
    """
    if model is None or processor is None:
        model, processor = _load_wavlm_model()

    waveform, sample_rate = _load_audio(wav_path)

    # Process audio
    inputs = processor(
        waveform, sampling_rate=sample_rate, return_tensors="pt", padding=True
    )

    with torch.no_grad():
        logits = model(inputs.input_values).logits

    # Decode (simplified - actual CTC decoding is more complex)
    vocab_size = logits.shape[-1]
    phoneme_ids = _decode_ctc_phonemes(logits, processor, vocab_size)

    # Estimate timestamps (rough - each frame is ~20ms)
    frame_duration = 0.02  # seconds
    timestamps = [i * frame_duration for i in range(len(phoneme_ids))]

    # Map token IDs back to labels (this is simplified)
    # In practice, you'd use processor.tokenizer.decode or a phoneme vocabulary
    phonemes = [f"PHON_{pid}" for pid in phoneme_ids]

    return phonemes, timestamps


def compare_phonemes(
    expected: List[str], detected: List[str], threshold: float = 0.7
) -> float:
    """
    Compare expected vs detected phonemes and return similarity score.
    Uses simple sequence alignment.
    """
    n, m = len(expected), len(detected)
    if n == 0 and m == 0:
        return 1.0
    if n == 0 or m == 0:
        return 0.0

    # Simple Levenshtein-based similarity
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if expected[i - 1] == detected[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost
            )

    edit_distance = dp[n][m]
    max_len = max(n, m)
    similarity = 1.0 - (edit_distance / max_len) if max_len > 0 else 0.0
    return similarity


def assess_pronunciation_wavlm(
    wav_path: str,
    reference_text: str,
    *,
    confidence_threshold: float = 0.6,  # Looser threshold for noisy audio
    phoneme_dict: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
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
    if not WAVLM_AVAILABLE:
        raise ImportError(
            f"Required libraries not installed: {WAVLM_IMPORT_ERROR}\n"
            "Install with: pip install torch transformers soundfile numpy"
        )

    model, processor = _load_wavlm_model()

    # Extract phonemes from audio
    detected_phonemes, phoneme_timestamps = extract_phonemes_wavlm(
        wav_path, model=model, processor=processor
    )

    # Get expected phonemes from reference text
    expected_phonemes = _text_to_phonemes(reference_text, phoneme_dict)

    # Simple word-level assessment (this is simplified)
    # In practice, you'd align phonemes to words and assess per word
    words = re.findall(r"\b\w+\b", reference_text.lower())
    results: List[Dict[str, Any]] = []

    # Rough word-level timing (divide audio duration by word count)
    if phoneme_timestamps:
        total_duration = phoneme_timestamps[-1] if phoneme_timestamps else 1.0
    else:
        total_duration = 1.0

    word_duration = total_duration / len(words) if words else 1.0

    # Overall phoneme similarity
    overall_similarity = compare_phonemes(expected_phonemes, detected_phonemes)

    for i, word in enumerate(words):
        # Use overall similarity as proxy (in practice, align phonemes to words)
        confidence = overall_similarity
        status = "correct" if confidence >= confidence_threshold else "mispronounced"

        start_time = i * word_duration
        end_time = (i + 1) * word_duration

        results.append(
            {
                "word": word,
                "start": start_time,
                "end": end_time,
                "confidence": confidence,
                "status": status,
            }
        )

    return results


if __name__ == "__main__":
    # Example usage
    wav_path = "input.wav"
    reference_text = "bicycle racing is the"
    results = assess_pronunciation_wavlm(wav_path, reference_text)
    for r in results:
        print(r)
