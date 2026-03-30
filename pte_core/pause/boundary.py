"""Boundary realization heuristics for read-aloud punctuation scoring."""
from __future__ import annotations

import re
from statistics import median
from typing import Any, Dict, List


_NON_SPEECH = {"sil", "sp", "spn", ""}
_FRICATIVE_PHONES = {
    "s",
    "z",
    "sh",
    "zh",
    "f",
    "v",
    "th",
    "dh",
}


def _normalize_phone(label: str) -> str:
    base = re.sub(r"\d+", "", str(label or "").strip().lower())
    return base


def estimate_boundary_realization(
    prev_word_phones: List[Dict[str, Any]],
    all_phones: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Estimate whether a boundary was signaled even without a clean silent gap.

    This is intentionally heuristic. The first production version only uses
    phone-duration evidence because it is available from MFA today.
    """
    valid_phone_durations = []
    for phone in all_phones or []:
        label = _normalize_phone(phone.get("label") or phone.get("word") or phone.get("value") or "")
        start = phone.get("start")
        end = phone.get("end")
        if label in _NON_SPEECH or start is None or end is None or end <= start:
            continue
        valid_phone_durations.append(end - start)

    baseline = median(valid_phone_durations) if valid_phone_durations else 0.08

    last_phone = None
    for phone in reversed(prev_word_phones or []):
        label = _normalize_phone(phone.get("label") or phone.get("word") or phone.get("value") or "")
        start = phone.get("start")
        end = phone.get("end")
        if label in _NON_SPEECH or start is None or end is None or end <= start:
            continue
        last_phone = {
            "label": label,
            "duration": end - start,
        }
        break

    if not last_phone:
        return {
            "score": 0.0,
            "classification": "none",
            "reason": "no_final_phone",
            "baseline_phone_duration": round(baseline, 3),
        }

    duration = last_phone["duration"]
    ratio = duration / max(baseline, 0.04)
    is_fricative = last_phone["label"] in _FRICATIVE_PHONES

    score = 0.0
    classification = "none"
    reason = "no_lengthening"

    if is_fricative and duration >= 0.12 and ratio >= 1.5:
        score = min(1.0, 0.55 + 0.20 * (ratio - 1.5))
        classification = "strong" if score >= 0.75 else "moderate"
        reason = "final_fricative_lengthening"
    elif duration >= 0.14 and ratio >= 1.8:
        score = min(0.7, 0.35 + 0.15 * (ratio - 1.8))
        classification = "moderate" if score >= 0.5 else "weak"
        reason = "final_segment_lengthening"

    return {
        "score": round(max(0.0, score), 3),
        "classification": classification,
        "reason": reason,
        "final_phone": last_phone["label"],
        "final_phone_duration": round(duration, 3),
        "baseline_phone_duration": round(baseline, 3),
        "lengthening_ratio": round(ratio, 3),
    }
