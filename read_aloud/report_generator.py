from __future__ import annotations

from typing import Any, Dict, List, Optional

from pause.hesitation import aggregate_pause_penalty
from pause.rules import MAX_PUNCTUATION_PENALTY, PAUSE_PUNCTUATION
from pte_pronunciation import (
    pronunciation_score_0_100,
    pte_pronunciation_band,
    generate_feedback_strings,
)


def merge_content_and_pronunciation(
    content_results: List[Dict[str, Any]],
    pronunciation_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge content alignment results with pronunciation assessment.

    Content results come from word_level_matcher (status: correct, missed, substituted, repeated).
    Pronunciation results come from MFA or WavLM (status: correct, mispronounced).

    Decision rules:
    - MISSED: word in reference but not in ASR → status="missed"
    - REPEATED: extra word in ASR → status="repeated"
    - MISPRONOUNCED: word aligned but pronunciation confidence < threshold → status="mispronounced"
    - CORRECT: word aligned and pronunciation confidence >= threshold → status="correct"

    Args:
        content_results: List from word_level_matcher with {word, status, start, end, ...}
        pronunciation_results: List from MFA/WavLM with {word, start, end, confidence, status}

    Returns:
        Unified report: List of {word, status, start, end, confidence}
    """
    # Create lookup: word -> pronunciation result
    # Match by word text (normalized)
    pron_dict: Dict[str, Dict[str, Any]] = {}
    for pron in pronunciation_results:
        word_key = pron.get("word", "").lower().strip()
        if word_key:
            pron_dict[word_key] = pron

    unified: List[Dict[str, Any]] = []

    for content in content_results:
        word = content.get("word", "")
        content_status = content.get("status", "")

        # Content-level errors take precedence
        if content_status == "missed":
            unified.append(
                {
                    "word": word,
                    "status": "missed",
                    "start": None,
                    "end": None,
                    "confidence": 0.0,
                }
            )
        elif content_status == "repeated":
            unified.append(
                {
                    "word": word,
                    "status": "repeated",
                    "start": content.get("start"),
                    "end": content.get("end"),
                    "confidence": 0.0,
                }
            )
        elif content_status == "substituted":
            # Substituted words are content errors
            unified.append(
                {
                    "word": word,
                    "status": "substituted",
                    "start": content.get("start"),
                    "end": content.get("end"),
                    "confidence": 0.0,
                    "spoken": content.get("spoken"),
                }
            )
        elif content_status == "correct":
            # Word was aligned correctly - check pronunciation
            word_key = word.lower().strip()
            pron_result = pron_dict.get(word_key)

            if pron_result:
                # Use pronunciation assessment
                pron_status = pron_result.get("status", "mispronounced")
                confidence = pron_result.get("confidence", 0.0)

                # Use timestamps from content (ASR) if available, otherwise from pronunciation
                start = content.get("start") or pron_result.get("start")
                end = content.get("end") or pron_result.get("end")

                merged: Dict[str, Any] = {
                    "word": word,
                    "status": pron_status,  # "aligned"/"mispronounced" from MFA; treated as pronunciation label
                    "start": start,
                    "end": end,
                    "confidence": confidence,
                }
                # Preserve any extra, explainable fields from pronunciation backend (DP, PTE summary, etc.)
                for k, v in pron_result.items():
                    if k in {"word", "status", "start", "end", "confidence"}:
                        continue
                    merged[k] = v
                unified.append(merged)
            else:
                # Word aligned but no pronunciation result - default to correct
                unified.append(
                    {
                        "word": word,
                        "status": "correct",
                        "start": content.get("start"),
                        "end": content.get("end"),
                        "confidence": 1.0,  # Default confidence
                    }
                )
        else:
            # Unknown status - include as-is
            unified.append(content)

    return unified


def generate_final_report(
    content_results: List[Dict[str, Any]],
    pronunciation_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate final unified report with statistics.

    Args:
        content_results: Content alignment results
        pronunciation_results: Pronunciation assessment results

    Returns:
        Dict with 'words' (list) and 'summary' (stats dict)
    """
    words = merge_content_and_pronunciation(content_results, pronunciation_results)

    # Rhythm score from pause penalties (if punctuation tokens exist)
    pause_results = [w for w in words if w.get("word") in PAUSE_PUNCTUATION]
    pause_penalty = aggregate_pause_penalty(pause_results, max_penalty=MAX_PUNCTUATION_PENALTY)
    rhythm_score = max(0.0, min(1.0, 1.0 - (pause_penalty / MAX_PUNCTUATION_PENALTY))) if MAX_PUNCTUATION_PENALTY > 0 else 1.0

    # Calculate statistics
    total_words = len(words)
    correct = sum(1 for w in words if w.get("status") == "correct")
    mispronounced = sum(1 for w in words if w.get("status") == "mispronounced")
    missed = sum(1 for w in words if w.get("status") == "missed")
    repeated = sum(1 for w in words if w.get("status") == "repeated")
    substituted = sum(1 for w in words if w.get("status") == "substituted")

    # Average confidence for correctly pronounced words
    correct_confidences = [
        w.get("confidence", 0.0) for w in words if w.get("status") == "correct"
    ]
    avg_confidence = (
        sum(correct_confidences) / len(correct_confidences)
        if correct_confidences
        else 0.0
    )

    summary = {
        "total_words": total_words,
        "correct": correct,
        "mispronounced": mispronounced,
        "missed": missed,
        "repeated": repeated,
        "substituted": substituted,
        "accuracy": (correct / total_words * 100.0) if total_words > 0 else 0.0,
        "average_confidence": avg_confidence,
        "rhythm_score": rhythm_score,
        "pause_penalty": pause_penalty,
    }

    # If MFA pronunciation attached a PTE summary, update it with rhythm and recompute final score/band/feedback.
    pte_summary = None
    for w in words:
        if isinstance(w.get("pte_summary"), dict):
            pte_summary = w["pte_summary"]
            break

    if isinstance(pte_summary, dict):
        pte_summary = dict(pte_summary)  # copy
        pte_summary["rhythm"] = rhythm_score
        score_pte = pronunciation_score_0_100(
            phone=float(pte_summary.get("phone", 0.0) or 0.0),
            stress=float(pte_summary.get("stress", 0.0) or 0.0),
            rhythm=float(pte_summary.get("rhythm", 1.0) or 1.0),
            consistency_bonus=float(pte_summary.get("consistency_bonus", 0.0) or 0.0),
        )
        pte_summary["score_pte"] = score_pte  # PTE scale: 10-90
        pte_summary["pte_band"] = pte_pronunciation_band(score_pte)
        pte_summary["feedback"] = generate_feedback_strings(pte_summary)

        summary["pte_pronunciation"] = pte_summary

        # Keep words' embedded pte_summary in sync
        for w in words:
            if "pte_summary" in w and isinstance(w["pte_summary"], dict):
                w["pte_summary"] = pte_summary

    return {"words": words, "summary": summary}


if __name__ == "__main__":
    # Example usage
    content_results = [
        {"word": "bicycle", "status": "correct", "start": 0.42, "end": 0.91},
        {"word": "racing", "status": "correct", "start": 0.92, "end": 1.41},
        {"word": "is", "status": "missed", "start": None, "end": None},
        {"word": "the", "status": "correct", "start": 1.42, "end": 1.71},
    ]

    pronunciation_results = [
        {
            "word": "bicycle",
            "status": "mispronounced",
            "start": 0.40,
            "end": 0.90,
            "confidence": 0.43,
        },
        {
            "word": "racing",
            "status": "correct",
            "start": 0.91,
            "end": 1.40,
            "confidence": 0.85,
        },
        {
            "word": "the",
            "status": "correct",
            "start": 1.41,
            "end": 1.70,
            "confidence": 0.90,
        },
    ]

    report = generate_final_report(content_results, pronunciation_results)
    print("Final Report:")
    print(report["summary"])
    print("\nWords:")
    for w in report["words"]:
        print(w)
