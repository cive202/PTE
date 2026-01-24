from __future__ import annotations

from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pte_tools import (
    voice2text,
    assess_pronunciation_mfa,
    is_audio_clear,
    generate_final_report,
    assess_pronunciation_wavlm,
    word_level_matcher
)


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
    # Step 1: Run ASR
    asr_result = voice2text(wav_path)
    asr_words = asr_result.get("word_timestamps", [])
    
    # Calculate average ASR confidence if available
    # Note: Parakeet may not provide confidence scores directly
    # For now, we'll estimate based on whether words were detected
    asr_confidence = None
    if asr_words:
        # Simple heuristic: if we got words, assume reasonable confidence
        # In practice, extract actual confidence from ASR output if available
        asr_confidence = 0.8  # Placeholder - should be extracted from ASR

    # Step 2: Word-level matching (content alignment)
    content_results = word_level_matcher(wav_path, reference_text)

    # Step 3: Detect audio clarity
    audio_clear, quality_metrics = is_audio_clear(
        wav_path,
        asr_confidence=asr_confidence,
        silence_ratio_threshold=silence_ratio_threshold,
        asr_confidence_threshold=asr_confidence_threshold,
    )

    # Step 4: Pronunciation assessment based on audio clarity
    if audio_clear:
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
        except Exception as e:
            # Fallback to WavLM if MFA fails
            print(f"Warning: MFA failed ({e}), falling back to WavLM")
            pronunciation_results = assess_pronunciation_wavlm(
                wav_path,
                reference_text,
                confidence_threshold=pronunciation_threshold_noisy,
            )
            pronunciation_method = "wavlm_fallback"
    else:
        # Use WavLM-CTC for noisy audio
        pronunciation_results = assess_pronunciation_wavlm(
            wav_path,
            reference_text,
            confidence_threshold=pronunciation_threshold_noisy,
        )
        pronunciation_method = "wavlm"

    # Step 5: Generate unified report
    final_report = generate_final_report(content_results, pronunciation_results)

    # Add metadata
    final_report["audio_clear"] = audio_clear
    final_report["pronunciation_method"] = pronunciation_method
    final_report["quality_metrics"] = {
        "silence_ratio": quality_metrics.silence_ratio,
        "rms_mean": quality_metrics.rms_mean,
        "duration_s": quality_metrics.duration_s,
    }

    return final_report


def assess_pte_simple(
    wav_path: str, reference_text: str
) -> Dict[str, Any]:
    """
    Simplified interface with default parameters.

    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription text

    Returns:
        Unified report dict (same format as assess_pte)
    """
    return assess_pte(wav_path, reference_text)


if __name__ == "__main__":
    # Example usage
    wav_path = "input.wav"
    reference_text = "bicycle racing is the"

    print("Running PTE pipeline...")
    result = assess_pte_simple(wav_path, reference_text)

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

    print(f"\nAudio clear: {result['audio_clear']}")
    print(f"Pronunciation method: {result['pronunciation_method']}")

    print("\n=== Word-level Results ===")
    for word_result in result["words"][:10]:  # Show first 10
        print(
            f"{word_result['word']}: {word_result['status']} "
            f"(start={word_result.get('start')}, end={word_result.get('end')}, "
            f"confidence={word_result.get('confidence', 0.0):.2f})"
        )
