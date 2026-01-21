from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from voice2text import words_timestamps


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    # keep apostrophes inside words, drop other punctuation
    token = re.sub(r"[^a-z0-9']+", "", token)
    return token


def tokenize_reference(text: str) -> List[str]:
    # Split on whitespace then normalize
    raw = re.split(r"\s+", text.strip())
    tokens = [_normalize_token(t) for t in raw if _normalize_token(t)]
    return tokens


@dataclass(frozen=True)
class AlignedWord:
    ref_word: Optional[str]
    hyp_word: Optional[str]
    op: str  # "match" | "sub" | "del" | "ins"
    hyp_start: Optional[float] = None
    hyp_end: Optional[float] = None


def _align_sequences(
    ref: Sequence[str], hyp: Sequence[str]
) -> List[Tuple[str, Optional[int], Optional[int]]]:
    """
    Classic edit-distance alignment returning a path of operations.

    Returns list of tuples: (op, ref_index, hyp_index)
      op in {"match","sub","del","ins"}.
    """
    n, m = len(ref), len(hyp)
    # dp costs
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back: List[List[Tuple[str, int, int]]] = [[("start", -1, -1)] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = ("del", i - 1, None)  # type: ignore[arg-type]
    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = ("ins", None, j - 1)  # type: ignore[arg-type]

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost_sub = 0 if ref[i - 1] == hyp[j - 1] else 1
            candidates = [
                (dp[i - 1][j] + 1, ("del", i - 1, None)),
                (dp[i][j - 1] + 1, ("ins", None, j - 1)),
                (dp[i - 1][j - 1] + cost_sub, ("match" if cost_sub == 0 else "sub", i - 1, j - 1)),
            ]
            best_cost, best_step = min(candidates, key=lambda x: x[0])
            dp[i][j] = best_cost
            back[i][j] = best_step  # type: ignore[assignment]

    # backtrack
    ops: List[Tuple[str, Optional[int], Optional[int]]] = []
    i, j = n, m
    while not (i == 0 and j == 0):
        op, ri, hj = back[i][j]
        ops.append((op, ri, hj))  # type: ignore[arg-type]
        if op in ("match", "sub"):
            i -= 1
            j -= 1
        elif op == "del":
            i -= 1
        elif op == "ins":
            j -= 1
        else:
            break
    ops.reverse()
    return ops


def align_reference_to_asr(
    reference_text: str, asr_words: List[Dict[str, Any]]
) -> List[AlignedWord]:
    """
    Align reference tokens to ASR word list (each item like {start,end,word}).
    """
    ref_tokens = tokenize_reference(reference_text)
    hyp_tokens = [_normalize_token(w.get("word", "")) for w in asr_words if _normalize_token(w.get("word", ""))]

    # Map hyp token index to original asr_words entry with timestamps.
    hyp_entries: List[Dict[str, Any]] = []
    for w in asr_words:
        t = _normalize_token(w.get("word", ""))
        if t:
            hyp_entries.append(w)

    ops = _align_sequences(ref_tokens, hyp_tokens)
    aligned: List[AlignedWord] = []
    for op, ri, hj in ops:
        ref_word = ref_tokens[ri] if ri is not None else None
        hyp_word = hyp_tokens[hj] if hj is not None else None
        hyp_start = hyp_entries[hj].get("start") if hj is not None else None
        hyp_end = hyp_entries[hj].get("end") if hj is not None else None
        aligned.append(AlignedWord(ref_word=ref_word, hyp_word=hyp_word, op=op, hyp_start=hyp_start, hyp_end=hyp_end))
    return aligned


def word_level_matcher(file_path: str, reference_text: str) -> List[Dict[str, Any]]:
    """
    Core content-alignment output used by the rest of the system.

    Returns list of dicts:
      - For ref words: {word, status, start, end}
      - status in {"correct","missed","substituted","repeated"}

    Notes:
      - "missed" comes from deletions (ref token not spoken)
      - "repeated" comes from insertions (extra spoken token)
      - "substituted" comes from substitutions
    """
    asr = words_timestamps(file_path)
    aligned = align_reference_to_asr(reference_text, asr)

    out: List[Dict[str, Any]] = []
    for a in aligned:
        if a.op == "match":
            out.append({"word": a.ref_word, "status": "correct", "start": a.hyp_start, "end": a.hyp_end})
        elif a.op == "del":
            out.append({"word": a.ref_word, "status": "missed", "start": None, "end": None})
        elif a.op == "sub":
            out.append(
                {
                    "word": a.ref_word,
                    "status": "substituted",
                    "start": a.hyp_start,
                    "end": a.hyp_end,
                    "spoken": a.hyp_word,
                }
            )
        elif a.op == "ins":
            out.append({"word": a.hyp_word, "status": "repeated", "start": a.hyp_start, "end": a.hyp_end})

    return out


if __name__ == "__main__":
    file_path = "input.wav"
    reference_text = "bicycle racing is the"
    print(word_level_matcher(file_path, reference_text))
