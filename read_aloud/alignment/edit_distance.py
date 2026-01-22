"""Edit distance alignment algorithm for sequence matching."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple


def align_sequences(
    ref: Sequence[str], hyp: Sequence[str]
) -> List[Tuple[str, Optional[int], Optional[int]]]:
    """Classic edit-distance alignment returning a path of operations.

    Returns list of tuples: (op, ref_index, hyp_index)
      op in {"match","sub","del","ins"}.

      match -> correct words
      del -> missed words 
      ins -> extra words
      
    Args:
        ref: Reference sequence (list of tokens)
        hyp: Hypothesis sequence (list of tokens from ASR)
        
    Returns:
        List of tuples: (operation, ref_index, hyp_index)
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
