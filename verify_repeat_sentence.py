
import sys
import os
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.absolute()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the module to test
from repeat_sentence.pte_pipeline import assess_repeat_sentence

# Mock data for ASR
MOCK_ASR_WORDS = [
    {"word": "Higher", "start": 0.5, "end": 0.9},
    {"word": "education", "start": 1.0, "end": 1.8},
    {"word": "prepares", "start": 1.9, "end": 2.5},
    {"word": "students", "start": 2.6, "end": 3.2},
    {"word": "for", "start": 3.3, "end": 3.5},
    {"word": "professional", "start": 3.6, "end": 4.5},
    {"word": "challenges", "start": 4.6, "end": 5.2}
]

def mock_get_words_timestamps():
    print("  [Mock] Returning mocked ASR word timestamps...")
    return MOCK_ASR_WORDS

def mock_voice2text(file_path):
    print(f"  [Mock] voice2text called for {file_path}")
    return {
        "text": "Higher education prepares students for professional challenges",
        "word_timestamps": MOCK_ASR_WORDS,
        "char_timestamps": [],
        "segment_timestamps": []
    }

def run_test():
    print("=== Verifying Repeat Sentence Pipeline (with Mocked ASR) ===")
    
    # Paths
    wav_path = os.path.join(ROOT_DIR, "corpus", "utt1", "Education.wav")
    ref_text = "Higher education prepares students for professional challenges."
    
    if not os.path.exists(wav_path):
        print(f"Error: Test file not found: {wav_path}")
        return

    print(f"Audio: {wav_path}")
    print(f"Ref Text: {ref_text}")
    print("\nStarting pipeline...")

    # Mock MFA result
    MOCK_MFA_RESULT = {
        "words": [
            {"word": "Higher", "start": 0.5, "end": 0.9, "status": "aligned", "confidence": 0.95},
            {"word": "education", "start": 1.0, "end": 1.8, "status": "aligned", "confidence": 0.92},
            {"word": "prepares", "start": 1.9, "end": 2.5, "status": "aligned", "confidence": 0.90},
            {"word": "students", "start": 2.6, "end": 3.2, "status": "aligned", "confidence": 0.94},
            {"word": "for", "start": 3.3, "end": 3.5, "status": "aligned", "confidence": 0.98},
            {"word": "professional", "start": 3.6, "end": 4.5, "status": "aligned", "confidence": 0.91},
            {"word": "challenges", "start": 4.6, "end": 5.2, "status": "aligned", "confidence": 0.89}
        ],
        "phones": [],
        "pte_pronunciation": {
            "score_pte": 85,
            "pte_band": "High",
            "phone": 0.9,
            "stress": 0.8,
            "rhythm": 0.85,
            "consistency_bonus": 1.0
        }
    }

    def mock_assess_pronunciation_mfa(*args, **kwargs):
        print("  [Mock] assess_pronunciation_mfa called")
        return [
            {**w, "status": "correct", "confidence": w["confidence"]} 
            for w in MOCK_MFA_RESULT["words"]
        ]

    # Patch ASR components AND MFA
    # Note: Must patch where they are USED, not where they are defined
    # word_level_matcher imports get_words_timestamps, so we must patch it in word_level_matcher's namespace
    with patch("read_aloud.scorer.word_level_matcher.get_words_timestamps", side_effect=mock_get_words_timestamps), \
         patch("repeat_sentence.pte_pipeline.voice2text", side_effect=mock_voice2text), \
         patch("repeat_sentence.pte_pipeline.assess_pronunciation_mfa", side_effect=mock_assess_pronunciation_mfa), \
         patch("repeat_sentence.pte_pipeline.is_audio_clear", return_value=(True, MagicMock(silence_ratio=0.1, rms_mean=0.05, duration_s=5.5))):
        
        try:
            # Run the assessment
            result = assess_repeat_sentence(
                wav_path=wav_path,
                reference_text=ref_text,
                mfa_acoustic_model="english_us_arpa", # Use US ARPA as default
                mfa_dictionary="english_us_arpa"
            )
            
            print("\n=== Pipeline Execution Successful ===")
            print("\nSummary Stats:")
            summary = result.get("summary", {})
            print(json.dumps(summary, indent=2))
            
            print("\nWord Details (First 3):")
            for w in result.get("words", [])[:3]:
                print(f" - {w['word']}: {w['status']} (Conf: {w.get('confidence', 0.0):.2f})")
                
            # Verification checks
            # Total words = 7 words + 1 punctuation (period)
            assert summary["total_words"] == 8
            assert summary["correct"] >= 7 # 7 words correct
            print("\n✅ Verification PASSED: Structure and Logic are sound.")
            
        except Exception as e:
            print(f"\n❌ Verification FAILED with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_test()
