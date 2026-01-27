import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from describe_image.evaluator import DescribeImageEvaluator

def test_pipeline():
    # Use an existing wav file from the project
    # Trying to find a valid wav file in the known structure
    candidates = [
        "PTE_MFA_TESTER_DOCKER/data/Cs_degree.wav",
        "PTE_MFA_TESTER_DOCKER/old_data/Education.wav"
    ]
    
    wav_path = None
    for c in candidates:
        p = Path(__file__).parent.parent / c
        if p.exists():
            wav_path = str(p.absolute())
            break
            
    if not wav_path:
        print("No test audio file found. Please check paths.")
        return

    print(f"Testing with audio: {wav_path}")

    image_schema = {
        "image_type": "bar_chart",
        "description": "A dummy chart for testing.",
        "key_points": ["Point 1", "Point 2"]
    }

    evaluator = DescribeImageEvaluator()
    try:
        result = evaluator.evaluate(wav_path, image_schema)
        print("\n--- Evaluation Successful ---")
        print(f"Transcript: {result['transcript']}")
        print(f"Grammar Issues Found: {len(result['grammar_issues'])}")
        print(f"Algorithmic Fluency Score: {result['algorithmic_scores'].get('fluency_score')}")
        print(f"Algorithmic Pronunciation Score: {result['algorithmic_scores'].get('pronunciation_score')}")
        print(f"LLM Response: {result['llm_evaluation'].get('overall_assessment')}")
        
        # Print the prompt to verify it looks correct
        print("\n--- Generated Prompt Preview (First 500 chars) ---")
        print(result["prompt_used"][:500])
        print("...")

    except Exception as e:
        print(f"Evaluation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline()
