"""Test PTE pipeline with a sample WAV file."""
import sys
sys.path.insert(0, "read_aloud")

from pte_pipeline import assess_pte_simple

# Replace with your actual paths
wav_path = r"c:\Users\Acer\DataScience\PTE\corpus\utt1\Education.wav"
reference_text = (
    "Higher education prepares students for professional challenges by developing "
    "analytical and communication skills. Online platforms offer flexibility, but "
    "curriculum quality must remain consistent. Universities emphasize research, "
    "innovation, and collaboration across disciplines."
)

print("=== Running PTE Pipeline ===\n")
print(f"Audio: {wav_path}")
print(f"Reference: {reference_text[:50]}...\n")

try:
    result = assess_pte_simple(wav_path, reference_text)
    
    print("=== Summary ===")
    summary = result.get("summary", {})
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    # Check for PTE pronunciation summary
    pte = summary.get("pte_pronunciation")
    if pte:
        print("\n=== PTE Pronunciation Score ===")
        print(f"Score (10-90): {pte.get('score_pte', 'N/A')}")
        print(f"Band: {pte.get('pte_band', 'N/A')}")
        print(f"Phone Intelligibility: {pte.get('phone', 0):.2f}")
        print(f"Stress Accuracy: {pte.get('stress', 0):.2f}")
        print(f"Rhythm Score: {pte.get('rhythm', 0):.2f}")
        print(f"Consistency Bonus: {pte.get('consistency_bonus', 0):.2f}")
        
        print("\n=== Feedback ===")
        for msg in pte.get("feedback", []):
            print(f"  • {msg}")
    else:
        print("\n(PTE pronunciation summary not available - MFA may not have run)")
    
    print(f"\n=== Audio Quality ===")
    print(f"Audio clear: {result.get('audio_clear', 'N/A')}")
    print(f"Pronunciation method: {result.get('pronunciation_method', 'N/A')}")
    
    print(f"\n=== First 10 Words ===")
    for w in result.get("words", [])[:10]:
        status = w.get("status", "unknown")
        conf = w.get("confidence", 0.0)
        word = w.get("word", "")
        print(f"  {word}: {status} (confidence: {conf:.2f})")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
