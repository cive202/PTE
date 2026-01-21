from __future__ import annotations

from typing import Any, Dict, List, Optional


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

                unified.append(
                    {
                        "word": word,
                        "status": pron_status,  # "correct" or "mispronounced"
                        "start": start,
                        "end": end,
                        "confidence": confidence,
                    }
                )
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
    }

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
