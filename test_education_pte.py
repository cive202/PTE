"""Test PTE pipeline on Education.wav with reference text."""
import sys
sys.path.insert(0, "read_aloud")

from pte_pipeline import assess_pte_simple

# Your audio file
wav_path = r"c:\Users\Acer\DataScience\PTE\corpus\utt1\Education.wav"

# Reference text (what was displayed on screen)
reference_text = (
    "Higher education prepares students for professional challenges by developing "
    "analytical and communication skills. Online platforms offer flexibility, but "
    "curriculum quality must remain consistent. Universities emphasize research, "
    "innovation, and collaboration across disciplines."
)

print("Running PTE pipeline on Education.wav...")
print(f"Reference text: {reference_text[:50]}...")
print()

# Run full PTE assessment
result = assess_pte_simple(wav_path, reference_text)

# Print summary
print("=== PTE Summary ===")
summary = result.get("summary", {})
print(f"Total words: {summary.get('total_words', 0)}")
print(f"Correct: {summary.get('correct', 0)}")
print(f"Mispronounced: {summary.get('mispronounced', 0)}")
print(f"Missed: {summary.get('missed', 0)}")
print(f"Accuracy: {summary.get('accuracy', 0):.1f}%")
print()

# Print PTE pronunciation summary (if available)
pte = summary.get("pte_pronunciation")
if pte:
    print("=== PTE Pronunciation Score ===")
    print(f"Score (10-90 scale): {pte.get('score_pte', 0)}")
    print(f"PTE Band: {pte.get('pte_band', 0)}")
    print(f"Phone Intelligibility: {pte.get('phone', 0):.2f}")
    print(f"Stress Accuracy: {pte.get('stress', 0):.2f}")
    print(f"Rhythm Score: {pte.get('rhythm', 0):.2f}")
    print(f"Consistency Bonus: {pte.get('consistency_bonus', 0):.2f}")
    print()
    print("=== Feedback ===")
    for feedback_msg in pte.get("feedback", []):
        print(f"  • {feedback_msg}")
else:
    print("(PTE pronunciation summary not available - MFA may not have run)")
    print("Audio clear:", result.get("audio_clear", False))
    print("Pronunciation method:", result.get("pronunciation_method", "unknown"))

print()
print("=== First 10 Words ===")
for word in result.get("words", [])[:10]:
    status = word.get("status", "unknown")
    confidence = word.get("confidence", 0.0)
    print(f"  {word.get('word', '?')}: {status} (confidence: {confidence:.2f})")
