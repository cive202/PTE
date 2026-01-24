"""PTE-style phoneme DP alignment + scoring primitives.

This module is intentionally *explainable*:
- expected vs actual phoneme alignment (DP)
- stress-aware, vowel-weighted substitution costs
- word-final deletion discounts (accent-robust, not accent-specific)
- substitution pattern counting (consistency vs random errors)
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

try:
    from phonetics.accent_tolerance import (
        FINAL_VOICELESS_STOPS,
        FINAL_VOICED_STOPS,
        VOWELS,
    )
except ImportError:
    # Safe fallbacks for environments that import MFA without phonetics extras.
    FINAL_VOICELESS_STOPS = {"T", "K", "P"}  # type: ignore
    FINAL_VOICED_STOPS = {"D", "B", "G"}  # type: ignore
    VOWELS = {  # type: ignore
        "AA","AE","AH","AO","AW","AY","EH","ER","EY","IH","IY","OW","OY","UH","UW"
    }


# Directional substitution softness (expected -> actual).
# Values are COST MULTIPLIERS (lower = more forgiving), not similarities.
# Keep this table small and auditable.
PHONEME_SIMILARITY_COST_MULT: Dict[Tuple[str, str], float] = {
    ("TH", "T"): 0.4,
    ("TH", "D"): 0.4,
    ("DH", "D"): 0.4,
    ("DH", "T"): 0.5,
    ("V", "W"): 0.3,
    ("W", "V"): 0.6,  # directional
    ("Z", "S"): 0.4,
    ("ZH", "SH"): 0.5,
}


def base_phone(p: str) -> str:
    return (p or "").upper().rstrip("012")


def stress(p: str) -> int:
    p = (p or "").upper()
    if p.endswith("1"):
        return 1
    if p.endswith("2"):
        return 2
    return 0


def substitution_cost(exp: str, act: str) -> float:
    """Stress-aware, vowel-weighted, directional substitution cost.

    Returns cost in [0, +inf). 0 is perfect.
    """
    e = base_phone(exp)
    a = base_phone(act)

    if not e or not a:
        return 1.0
    if e == a:
        return 0.0

    base = 1.0

    # Directional softness for accent-robust substitutions
    mult = PHONEME_SIMILARITY_COST_MULT.get((e, a))
    if mult is not None:
        base *= mult

    # Vowel weighting (PTE: vowels matter more)
    if e in VOWELS:
        if stress(exp) == 1:
            base *= 1.4
        else:
            base *= 1.2

    return base


def deletion_cost(exp: str, is_word_final: bool) -> float:
    """Deletion cost with word-final discounts (accent-robust)."""
    e = base_phone(exp)
    base = 1.0
    if not e:
        return base
    if is_word_final:
        if e in FINAL_VOICELESS_STOPS:
            return base * 0.3
        if e in FINAL_VOICED_STOPS:
            return base * 0.7
    return base


def insertion_cost() -> float:
    return 1.0


def align_phonemes_with_dp(
    expected: List[str],
    observed: List[str],
    word: Optional[str] = None,
    accent_tolerant: bool = True,
) -> Tuple[List[Tuple[str, Optional[str], Optional[str]]], float, Dict[str, Any]]:
    """Align expected and observed phonemes using dynamic programming.
    
    Uses phoneme_cost for accent-tolerant alignment with intelligibility weighting
    and final stop deletion discounts.
    
    Args:
        expected: Expected phone sequence (from CMUdict)
        observed: Observed phone sequence (from MFA/WavLM)
        word: Optional word context (for function word detection)
        accent_tolerant: Whether to use accent-tolerant costs (default: True)
        
    Returns:
        Tuple of:
            - alignment_path: List of (op, expected_phone, observed_phone)
              where op in {"match", "sub", "del", "ins"}
            - total_cost: Weighted alignment cost
            - metadata: Dict with consistency patterns, etc.
    """
    # This DP is always available (no optional deps). `accent_tolerant` currently
    # just controls whether we apply the directional softness table.

    n, m = len(expected), len(observed)

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    back: List[List[Tuple[str, Optional[int], Optional[int]]]] = [
        [("start", None, None) for _ in range(m + 1)] for _ in range(n + 1)
    ]

    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + deletion_cost(expected[i - 1], is_word_final=(i == n))
        back[i][0] = ("del", i - 1, None)

    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + insertion_cost()
        back[0][j] = ("ins", None, j - 1)

    patterns: Counter[Tuple[str, str]] = Counter()

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            exp = expected[i - 1]
            act = observed[j - 1]

            sub_cost = substitution_cost(exp, act)
            if not accent_tolerant:
                # No directional softness; keep vowel stress weighting.
                e = base_phone(exp)
                a = base_phone(act)
                if e == a:
                    sub_cost = 0.0
                else:
                    sub_cost = 1.0
                    if e in VOWELS:
                        sub_cost *= 1.4 if stress(exp) == 1 else 1.2

            cand_sub = (dp[i - 1][j - 1] + sub_cost, ("match" if sub_cost == 0 else "sub", i - 1, j - 1))
            cand_del = (dp[i - 1][j] + deletion_cost(exp, is_word_final=(i == n)), ("del", i - 1, None))
            cand_ins = (dp[i][j - 1] + insertion_cost(), ("ins", None, j - 1))

            best_cost, best_step = min([cand_sub, cand_del, cand_ins], key=lambda x: x[0])
            dp[i][j] = best_cost
            back[i][j] = best_step

            if best_step[0] == "sub":
                e = base_phone(exp)
                a = base_phone(act)
                if e and a and e != a:
                    patterns[(e, a)] += 1
    
    alignment_path: List[Tuple[str, Optional[str], Optional[str]]] = []
    i, j = n, m
    while not (i == 0 and j == 0):
        op, ri, hj = back[i][j]
        if op in ("match", "sub"):
            alignment_path.append((op, expected[i - 1], observed[j - 1]))
            i -= 1
            j -= 1
        elif op == "del":
            alignment_path.append((op, expected[i - 1], None))
            i -= 1
        elif op == "ins":
            alignment_path.append((op, None, observed[j - 1]))
            j -= 1
        else:
            break
    alignment_path.reverse()

    total_cost = dp[n][m]
    max_cost = float(len(expected) + len(observed)) if (len(expected) + len(observed)) > 0 else 1.0

    metadata = {
        "total_cost": total_cost,
        "max_cost": max_cost,
        "patterns": dict(patterns),
        "alignment_length": len(alignment_path),
    }

    return alignment_path, total_cost, metadata


def _simple_align(
    expected: List[str],
    observed: List[str],
) -> Tuple[List[Tuple[str, Optional[str], Optional[str]]], float, Dict[str, Any]]:
    """Simple alignment fallback when accent tolerance is not available."""
    n, m = len(expected), len(observed)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j
    
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost_sub = 0 if expected[i - 1] == observed[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost_sub,
            )
    
    # Simple backtrack (simplified)
    alignment_path: List[Tuple[str, Optional[str], Optional[str]]] = []
    i, j = n, m
    
    while i > 0 or j > 0:
        if i > 0 and j > 0 and expected[i - 1] == observed[j - 1]:
            alignment_path.append(("match", expected[i - 1], observed[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or dp[i][j] == dp[i - 1][j] + 1):
            alignment_path.append(("del", expected[i - 1], None))
            i -= 1
        else:
            alignment_path.append(("ins", None, observed[j - 1]))
            j -= 1
    
    alignment_path.reverse()
    
    return alignment_path, float(dp[n][m]), {
        "total_cost": float(dp[n][m]),
        "max_cost": float(max(1, n + m)),
        "patterns": {},
        "alignment_length": len(alignment_path),
    }


def calculate_intelligibility_score(
    alignment_path: List[Tuple[str, Optional[str], Optional[str]]],
    metadata: Dict[str, Any],
    expected_len: Optional[int] = None,
) -> float:
    """Calculate intelligibility-weighted pronunciation score from alignment.
    
    Formula (PTE-style):
        Phone_Intelligibility = 1 - (total_cost / (expected_len * 1.2))
        
    Uses expected length * 1.2 as max_cost to account for reasonable insertions.
    
    Args:
        alignment_path: Alignment path from align_phonemes_with_dp
        metadata: Metadata from alignment (includes total_cost)
        expected_len: Expected phone sequence length (if None, uses max_cost from metadata)
        
    Returns:
        Intelligibility score (0.0-1.0)
    """
    total_cost = float(metadata.get("total_cost", 0.0) or 0.0)
    
    if expected_len is not None and expected_len > 0:
        max_cost = float(expected_len * 1.2)
    else:
        max_cost = float(metadata.get("max_cost", 1.0) or 1.0)
    
    if max_cost <= 0:
        return 1.0
    
    raw = 1.0 - (total_cost / max_cost)
    return max(0.0, min(1.0, raw))


def consistency_bonus(patterns: Counter[Tuple[str, str]] | Dict[Tuple[str, str], int]) -> float:
    """Additive consistency bonus for systematic accent patterns.
    
    PTE philosophy: consistent accent patterns (3+ occurrences) indicate
    stable accent, not random errors. Reward this with additive bonus.
    
    Formula: 0.02 * count per pattern, capped at 0.10 total.
    
    Args:
        patterns: Dict or Counter of (expected, actual) -> count
        
    Returns:
        Consistency bonus (0.0-0.10)
    """
    bonus = 0.0
    patterns_dict = patterns.items() if hasattr(patterns, "items") else []  # type: ignore[union-attr]
    
    for (e, a), count in patterns_dict:
        if count >= 3 and (e, a) in PHONEME_SIMILARITY_COST_MULT:
            # Systematic accent pattern detected
            bonus += 0.02 * count
    
    return min(bonus, 0.10)  # Cap at 10%


def extract_errors_and_patterns(
    alignment_path: List[Tuple[str, Optional[str], Optional[str]]],
) -> tuple[List[tuple[str, str]], Dict[tuple[str, str], int]]:
    """Extract errors and accent patterns from alignment path.
    
    Args:
        alignment_path: Alignment path from align_phonemes_with_dp
        
    Returns:
        Tuple of:
            - errors: List of (expected, observed) pairs for substitutions/deletions
            - accent_patterns: Counter of (expected_base, observed_base) -> count
    """
    errors: List[tuple[str, str]] = []
    accent_patterns: Counter[Tuple[str, str]] = Counter()
    
    for op, exp, obs in alignment_path:
        if not exp:
            continue
            
        e_base = base_phone(exp)
        
        if op == "sub":
            o_base = base_phone(obs) if obs else ""
            if e_base != o_base:
                errors.append((exp, obs if obs else "<eps>"))
                accent_patterns[(e_base, o_base)] += 1
        elif op == "del":
            errors.append((exp, "<eps>"))
    
    return errors, dict(accent_patterns)


def stress_accuracy(alignment_path: List[Tuple[str, Optional[str], Optional[str]]]) -> float:
    """Stress accuracy: correct base vowel on primary-stressed expected vowels."""
    total = 0
    correct = 0
    for op, exp, obs in alignment_path:
        if not exp:
            continue
        if base_phone(exp) in VOWELS and stress(exp) == 1:
            total += 1
            if obs and base_phone(exp) == base_phone(obs):
                correct += 1
    return 1.0 if total == 0 else (correct / total)
