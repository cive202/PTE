"""Pure stress-classification policy separate from acoustic extraction."""
from __future__ import annotations

from typing import Any, Dict


def classify_stress_result(stress_score: float, stress_details: Dict[str, Any] | None) -> Dict[str, Any]:
    details = stress_details if isinstance(stress_details, dict) else {}
    match_info = str(details.get("match_info", "") or "").strip()
    match_info_lc = match_info.lower()
    confidence = float(details.get("confidence", 0.0) or 0.0)

    stress_unknown = any(
        phrase in match_info_lc
        for phrase in (
            "insufficient phone evidence",
            "no reference pattern",
            "audio load error",
            "error:",
            "single syllable",
        )
    )

    stress_reliable = not stress_unknown and confidence >= 0.6
    stress_error = False

    if stress_reliable:
        stress_error = (
            stress_score < 0.85
            or "mismatch" in match_info_lc
            or "no vowels detected" in match_info_lc
        )
        if "perfect match" in match_info_lc or "acceptable variation" in match_info_lc:
            stress_error = False

    if not stress_reliable:
        return {
            "stress_reliable": False,
            "stress_error": False,
            "stress_level": "unknown",
            "stress_feedback": "Stress could not be measured reliably for this word.",
        }

    if stress_error:
        return {
            "stress_reliable": True,
            "stress_error": True,
            "stress_level": "error" if stress_score < 0.7 else "warn",
            "stress_feedback": match_info or "Stress pattern differs from expected emphasis.",
        }

    return {
        "stress_reliable": True,
        "stress_error": False,
        "stress_level": "ok",
        "stress_feedback": match_info or "Stress pattern is acceptable.",
    }
