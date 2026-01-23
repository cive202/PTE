"""PTE-style pronunciation aggregation, banding, and feedback.

This module aggregates explainable component scores into a single
PTE-like pronunciation score and generates user-facing feedback strings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def pronunciation_score_0_100(
    *,
    phone: float,
    stress: float,
    rhythm: float,
    consistency_bonus: float,
) -> float:
    """Final PTE-style pronunciation score (10-90 scale).
    
    Formula matches PTE scoring philosophy:
    - 55% phone intelligibility (core)
    - 25% stress accuracy (important)
    - 10% rhythm (fluency)
    - 10% consistency bonus (accent vs random errors)
    
    Returns score on PTE scale: 10-90 (not 0-100).
    """
    phone = _clamp01(phone)
    stress = _clamp01(stress)
    rhythm = _clamp01(rhythm)
    consistency_bonus = _clamp01(consistency_bonus)

    # PTE-style weighted combination
    score = (
        0.55 * phone +
        0.25 * stress +
        0.10 * rhythm +
        0.10 * consistency_bonus
    )
    
    # Map to PTE scale: 10-90 (as per spec: score * 90 + 10)
    # When score=1.0 (perfect): 1.0 * 90 + 10 = 100, but cap at 90 for PTE scale
    # When score=0.0 (worst): 0.0 * 90 + 10 = 10
    pte_score = score * 90 + 10
    return round(min(pte_score, 90.0), 1)  # Cap at 90 for PTE scale


def pte_pronunciation_band(score_0_100: float) -> int:
    """Map 0-100 score to a PTE-like band (empirical heuristic)."""
    s = score_0_100
    if s >= 90:
        return 90
    if 85 <= s <= 89.9:
        return 85
    if 80 <= s <= 84.9:
        return 79
    if 75 <= s <= 79.9:
        return 73
    if 70 <= s <= 74.9:
        return 65
    if 60 <= s <= 69.9:
        return 58
    if 50 <= s <= 59.9:
        return 50
    # Below 50: return a conservative 30–45 style range (use 45 cap)
    return 45 if s >= 45 else 30


def generate_feedback_strings(summary: Dict[str, Any]) -> List[str]:
    """Generate examiner-style feedback strings from component scores + patterns.
    
    Human-like feedback that:
    - Highlights consistent accent patterns (positive framing)
    - Points out specific errors (actionable)
    - Provides encouragement where appropriate
    """
    feedback: List[str] = []

    phone = float(summary.get("phone", 0.0) or 0.0)
    stress = float(summary.get("stress", 0.0) or 0.0)
    rhythm = float(summary.get("rhythm", 0.0) or 0.0)
    consistency_bonus = float(summary.get("consistency_bonus", 0.0) or 0.0)
    
    # Extract accent patterns and errors for specific feedback
    patterns = summary.get("patterns", {}) or {}
    errors = summary.get("errors", []) or []

    # 1. Positive framing: consistent accent patterns
    for pattern_key, count in patterns.items():
        if count >= 3:
            if isinstance(pattern_key, str) and "->" in pattern_key:
                e, a = pattern_key.split("->", 1)
                feedback.append(f"Consistent accent pattern: {e} pronounced as {a}")

    # 2. Positive: strong areas
    if stress >= 0.8 and phone >= 0.75:
        feedback.append("Your vowel clarity is strong, especially on stressed syllables.")
    elif phone >= 0.75:
        feedback.append("Your pronunciation is generally clear and easy to follow.")

    if consistency_bonus >= 0.06:
        feedback.append("Your pronunciation is consistent, indicating a stable accent.")

    # 3. Actionable improvements: specific errors
    for e, o in errors[:3]:  # Top 3 errors
        if o == "<eps>" or o is None:
            feedback.append(f"Missed sound: {e}")
        else:
            feedback.append(f"{e} sounded like {o}")

    # 4. General improvements
    if stress < 0.75:
        feedback.append("Try to maintain stress on important words for higher scores.")

    if rhythm < 0.75:
        feedback.append("Try to keep your rhythm smooth by avoiding long or frequent pauses.")

    # 5. Specific flags
    if summary.get("final_stop_drop_rate") is not None:
        rate = float(summary.get("final_stop_drop_rate") or 0.0)
        if rate >= 0.2:
            feedback.append("Final consonants are sometimes dropped, which slightly affects clarity.")

    # Keep list focused and actionable (max 5 items)
    return feedback[:5]

