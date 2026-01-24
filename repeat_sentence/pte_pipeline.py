"""PTE Repeat Sentence pipeline.

Similar to read_aloud, but optimized for single-sentence repetition:
- User hears a sentence (audio)
- User repeats the sentence
- System assesses: content accuracy + pronunciation quality

Reuses all the same modules via pte_tools:
- pte_core/mfa for pronunciation
- read_aloud/scorer for content alignment
- read_aloud/phonetics for CMUdict + accent tolerance
- read_aloud/pte_pronunciation for final scoring
"""
from __future__ import annotations

from typing import Any, Dict
import sys
from pathlib import Path

# Add project root to path to find pte_tools
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import tools from unified pte_tools
from pte_tools import (
    voice2text,
    assess_pronunciation_mfa,
    is_audio_clear,
    generate_final_report,
    assess_pronunciation_wavlm,
    word_level_matcher
)


def assess_repeat_sentence(
    wav_path: str,
    reference_text: str,
    *,
    asr_confidence_threshold: float = 0.75,
    silence_ratio_threshold: float = 0.35,
    pronunciation_threshold_clear: float = 0.75,
    pronunciation_threshold_noisy: float = 0.6,
    mfa_acoustic_model: str = "english_us_arpa",
    mfa_dictionary: str = "english_us_arpa",
    use_cmudict: bool = True,
    accent_tolerant: bool = True,
    intelligibility_floor: float = 0.55,
) -> Dict[str, Any]:
    """Assess Repeat Sentence task using full PTE pipeline.
    
    Flow:
    1. Run ASR to get spoken words + timestamps
    2. Tokenize and align reference text with ASR output (content matching)
    3. Detect audio clarity (ASR confidence + silence ratio)
    4. Route to MFA (clear audio) or WavLM-CTC (noisy audio) for pronunciation
    5. Generate unified word-level report with PTE-style pronunciation scores
    
    Args:
        wav_path: Path to audio file (user's repetition)
        reference_text: Reference sentence text (what was displayed/played)
        asr_confidence_threshold: Threshold for ASR confidence (default: 0.75)
        silence_ratio_threshold: Threshold for silence ratio (default: 0.35)
        pronunciation_threshold_clear: Pronunciation threshold for clear audio/MFA (default: 0.75)
        pronunciation_threshold_noisy: Pronunciation threshold for noisy audio/WavLM (default: 0.6)
        mfa_acoustic_model: MFA acoustic model name
        mfa_dictionary: MFA dictionary name
        use_cmudict: Whether to use CMUdict for expected phones (default: True)
        accent_tolerant: Whether to use accent-tolerant scoring (default: True)
        intelligibility_floor: Minimum score for intelligible speech (default: 0.55)
        
    Returns:
        Dict with:
            - "words": List of {word, status, start, end, confidence, ...}
            - "summary": Statistics dict with pte_pronunciation if available
            - "audio_clear": Whether audio was classified as clear
            - "pronunciation_method": "mfa" or "wavlm"
    """
    # Step 1: Run ASR
    asr_result = voice2text(wav_path)
    asr_words = asr_result.get("word_timestamps", [])
    
    # Calculate average ASR confidence if available
    asr_confidence = None
    if asr_words:
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
                use_cmudict=use_cmudict,
                accent_tolerant=accent_tolerant,
                intelligibility_floor=intelligibility_floor,
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


def assess_repeat_sentence_simple(
    wav_path: str,
    reference_text: str,
) -> Dict[str, Any]:
    """Simplified interface with default parameters.
    
    Args:
        wav_path: Path to audio file (user's repetition)
        reference_text: Reference sentence text
        
    Returns:
        Unified report dict (same format as assess_repeat_sentence)
    """
    return assess_repeat_sentence(wav_path, reference_text)


if __name__ == "__main__":
    # Example usage
    wav_path = "input.wav"
    reference_text = "Higher education prepares students for professional challenges."
    
    print("Running Repeat Sentence PTE pipeline...")
    result = assess_repeat_sentence_simple(wav_path, reference_text)
    
    print("\n=== Summary ===")
    summary = result["summary"]
    print(f"Total words: {summary['total_words']}")
    print(f"Correct: {summary['correct']}")
    print(f"Mispronounced: {summary['mispronounced']}")
    print(f"Missed: {summary['missed']}")
    print(f"Accuracy: {summary['accuracy']:.1f}%")
    
    # Print PTE pronunciation summary if available
    pte = summary.get("pte_pronunciation")
    if pte:
        print(f"\nPTE Pronunciation Score: {pte.get('score_pte', 0)}")
        print(f"PTE Band: {pte.get('pte_band', 0)}")
        print("Feedback:")
        for msg in pte.get("feedback", []):
            print(f"  • {msg}")
