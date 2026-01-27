import sys
from pathlib import Path
from typing import Dict, Any

# Ensure pte_core is importable
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from pte_core.mfa.pronunciation import assess_pronunciation_mfa
    MFA_AVAILABLE = True
except ImportError:
    MFA_AVAILABLE = False

def analyze_fluency_and_pronunciation(wav_path: str, transcript: str) -> Dict[str, Any]:
    """
    Analyze fluency and pronunciation using MFA alignment of the transcript to the audio.
    
    Args:
        wav_path: Path to the audio file.
        transcript: The text spoken (from ASR).
        
    Returns:
        Dict containing:
        - fluency_score (0-90)
        - pronunciation_score (0-90)
        - detailed_metrics (dict)
    """
    default_result = {
        "fluency_score": 10.0,
        "pronunciation_score": 10.0,
        "metrics": {}
    }

    if not transcript or not transcript.strip():
        return default_result

    if not MFA_AVAILABLE:
        print("Warning: MFA module not found. Returning default scores.")
        return default_result

    try:
        # Use MFA to align the spoken text to the audio
        # We assume the transcript is what was spoken, so we are measuring
        # HOW it was spoken (timing, clarity), not IF it was correct (content).
        results = assess_pronunciation_mfa(
            wav_path=wav_path,
            reference_text=transcript,
            acoustic_model="english_us_arpa", # Default to US
            dictionary="english_us_arpa",
            accent_tolerant=True
        )

        if not results:
            return default_result

        # Extract PTE-style scores if available (usually attached to the first word)
        pte_summary = results[0].get("pte_summary", {})
        
        # Pronunciation Score
        pron_score = pte_summary.get("score_pte", 10.0)
        
        # Fluency Score Calculation
        # MFA gives us timing metrics. We can compute a fluency score.
        # Check if pte_summary has rhythm or other metrics.
        # Alternatively, calculate from timing_metrics of the first word (shared)
        timing = results[0].get("timing_metrics", {})
        
        # Heuristic for Fluency:
        # 1. Speech Rate (phones/sec or words/min)
        # 2. Hesitations (detected by MFA)
        # 3. Pauses (silence)
        
        # For now, let's use the 'rhythm' component from PTE summary if available, 
        # or fall back to a simple mapping.
        rhythm_score = pte_summary.get("rhythm", 0.5) # 0.0 to 1.0
        
        # Map rhythm (0-1) to 10-90 range approx? 
        # Actually, let's look at the metrics.
        # words_per_min = timing.get("word_duration", {}).get("rate", 0) # pseudo-code
        
        # If 'rhythm' is already calculated by assess_pronunciation_mfa (it defaults to 1.0 in code I saw),
        # we might need to rely on our own logic if it's a placeholder.
        # The code I read showed rhythm=1.0 placeholder.
        
        # Let's trust pronunciation_score for Pronunciation.
        # For Fluency, let's use a placeholder 50 if we can't calculate it, 
        # or use pronunciation score as a proxy if they are correlated.
        # But better: Use the 'phone_rate' from timing metrics.
        phone_rate = timing.get("phone_rate", 0.0)
        # Typical phone rate: 10-15 phones/sec is fast. <5 is slow.
        # Map 3-12 range to 10-90.
        fluency_score = min(90, max(10, (phone_rate - 3) * (80/9) + 10))
        
        return {
            "fluency_score": round(fluency_score, 1),
            "pronunciation_score": round(pron_score, 1),
            "metrics": {
                "phone_rate": phone_rate,
                "pte_summary": pte_summary
            }
        }

    except Exception as e:
        print(f"Error in MFA analysis: {e}")
        return default_result
