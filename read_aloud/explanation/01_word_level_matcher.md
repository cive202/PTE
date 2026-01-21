# Line-by-Line Explanation: word_level_matcher.py

## Overview
This module performs sequence alignment between reference text and ASR output to detect content errors (missed words, repeated words, substitutions).

---

## Line-by-Line Breakdown

### Lines 1-7: Imports and Setup

```python
from __future__ import annotations
```
- **Purpose**: Enables forward references in type hints (Python 3.7+ feature)
- **Why**: Allows using types before they're defined

```python
import re
```
- **Purpose**: Import regex module for text pattern matching
- **Why**: Needed for tokenization and normalization

```python
from dataclasses import dataclass
```
- **Purpose**: Import dataclass decorator for structured data
- **Why**: Creates immutable data structures with less boilerplate

```python
from typing import Any, Dict, List, Optional, Sequence, Tuple
```
- **Purpose**: Import type hints for better code documentation
- **Why**: `Any` = any type, `Dict` = dictionary, `List` = list, `Optional` = can be None, `Sequence` = any sequence type, `Tuple` = tuple

```python
from voice2text import words_timestamps
```
- **Purpose**: Import ASR word timestamps function
- **Why**: Gets the spoken words with timestamps from audio

---

### Lines 10-14: Token Normalization Function

```python
def _normalize_token(token: str) -> str:
```
- **Purpose**: Normalize a single word token
- **Parameters**: `token` = word string
- **Returns**: Normalized lowercase word without punctuation

```python
    token = token.lower().strip()
```
- **Purpose**: Convert to lowercase and remove leading/trailing whitespace
- **Why**: Makes comparison case-insensitive and removes extra spaces

```python
    # keep apostrophes inside words, drop other punctuation
```
- **Purpose**: Comment explaining the regex pattern
- **Why**: Apostrophes are important for contractions (e.g., "don't")

```python
    token = re.sub(r"[^a-z0-9']+", "", token)
```
- **Purpose**: Remove all characters except lowercase letters, digits, and apostrophes
- **Regex breakdown**: `[^a-z0-9']+` means "one or more characters NOT in the set [a-z, 0-9, ']"
- **Why**: Standardizes tokens for comparison (removes punctuation, special chars)

```python
    return token
```
- **Purpose**: Return the normalized token
- **Why**: Completes the normalization process

---

### Lines 17-21: Reference Text Tokenization

```python
def tokenize_reference(text: str) -> List[str]:
```
- **Purpose**: Split reference text into normalized word tokens
- **Parameters**: `text` = full reference sentence
- **Returns**: List of normalized word tokens

```python
    # Split on whitespace then normalize
```
- **Purpose**: Comment explaining the process
- **Why**: Documents the two-step approach

```python
    raw = re.split(r"\s+", text.strip())
```
- **Purpose**: Split text by one or more whitespace characters
- **Regex**: `\s+` matches one or more whitespace (spaces, tabs, newlines)
- **Why**: Separates words while handling multiple spaces

```python
    tokens = [_normalize_token(t) for t in raw if _normalize_token(t)]
```
- **Purpose**: Normalize each token and filter out empty strings
- **List comprehension**: Creates list of normalized tokens, skipping empty ones
- **Why**: Ensures we only have valid word tokens

```python
    return tokens
```
- **Purpose**: Return the list of normalized tokens
- **Why**: Provides tokenized reference for alignment

---

### Lines 24-30: AlignedWord Data Class

```python
@dataclass(frozen=True)
```
- **Purpose**: Create immutable dataclass (cannot be modified after creation)
- **Why**: Prevents accidental changes to alignment results

```python
class AlignedWord:
```
- **Purpose**: Data structure representing one aligned word pair
- **Why**: Stores alignment information in a structured way

```python
    ref_word: Optional[str]
```
- **Purpose**: Reference word (can be None if word was inserted in ASR)
- **Why**: Tracks what word was expected

```python
    hyp_word: Optional[str]
```
- **Purpose**: Hypothesis word from ASR (can be None if word was deleted)
- **Why**: Tracks what word was actually spoken

```python
    op: str  # "match" | "sub" | "del" | "ins"
```
- **Purpose**: Operation type: match, substitution, deletion, or insertion
- **Why**: Categorizes the alignment operation

```python
    hyp_start: Optional[float] = None
```
- **Purpose**: Start time of hypothesis word in audio (seconds)
- **Why**: Provides temporal information for aligned words

```python
    hyp_end: Optional[float] = None
```
- **Purpose**: End time of hypothesis word in audio (seconds)
- **Why**: Completes temporal boundaries

---

### Lines 33-82: Sequence Alignment Algorithm

```python
def _align_sequences(
    ref: Sequence[str], hyp: Sequence[str]
) -> List[Tuple[str, Optional[int], Optional[int]]]:
```
- **Purpose**: Align reference and hypothesis sequences using edit distance
- **Parameters**: `ref` = reference tokens, `hyp` = hypothesis (ASR) tokens
- **Returns**: List of (operation, ref_index, hyp_index) tuples

```python
    """
    Classic edit-distance alignment returning a path of operations.
    
    Returns list of tuples: (op, ref_index, hyp_index)
      op in {"match","sub","del","ins"}.
    """
```
- **Purpose**: Docstring explaining the function
- **Why**: Documents the algorithm and return format

```python
    n, m = len(ref), len(hyp)
```
- **Purpose**: Get lengths of reference and hypothesis sequences
- **Why**: Needed for dynamic programming table dimensions

```python
    # dp costs
```
- **Purpose**: Comment indicating dynamic programming cost table
- **Why**: Documents the DP approach

```python
    dp = [[0] * (m + 1) for _ in range(n + 1)]
```
- **Purpose**: Create 2D array for edit distance costs
- **Dimensions**: (n+1) x (m+1) to include empty string cases
- **Why**: Stores minimum edit distance for each subproblem

```python
    back: List[List[Tuple[str, int, int]]] = [[("start", -1, -1)] * (m + 1) for _ in range(n + 1)]
```
- **Purpose**: Create backtracking table to reconstruct alignment path
- **Why**: Tracks which operation led to each cell for path reconstruction

```python
    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = ("del", i - 1, None)  # type: ignore[arg-type]
```
- **Purpose**: Initialize first column: deleting i reference words costs i
- **Why**: Base case: aligning reference to empty hypothesis requires deletions

```python
    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = ("ins", None, j - 1)  # type: ignore[arg-type]
```
- **Purpose**: Initialize first row: inserting j hypothesis words costs j
- **Why**: Base case: aligning empty reference to hypothesis requires insertions

```python
    for i in range(1, n + 1):
        for j in range(1, m + 1):
```
- **Purpose**: Fill DP table cell by cell
- **Why**: Computes optimal alignment for all subproblems

```python
            cost_sub = 0 if ref[i - 1] == hyp[j - 1] else 1
```
- **Purpose**: Cost of substitution: 0 if words match, 1 if different
- **Why**: Determines if current words align perfectly

```python
            candidates = [
                (dp[i - 1][j] + 1, ("del", i - 1, None)),
                (dp[i][j - 1] + 1, ("ins", None, j - 1)),
                (dp[i - 1][j - 1] + cost_sub, ("match" if cost_sub == 0 else "sub", i - 1, j - 1)),
            ]
```
- **Purpose**: Three possible operations: delete ref word, insert hyp word, or match/substitute
- **Why**: Explores all possible ways to reach current cell

```python
            best_cost, best_step = min(candidates, key=lambda x: x[0])
```
- **Purpose**: Choose operation with minimum cost
- **Why**: Greedy choice for optimal alignment

```python
            dp[i][j] = best_cost
            back[i][j] = best_step  # type: ignore[assignment]
```
- **Purpose**: Store optimal cost and operation for this cell
- **Why**: Saves solution for backtracking

```python
    # backtrack
```
- **Purpose**: Comment marking backtracking phase
- **Why**: Documents path reconstruction

```python
    ops: List[Tuple[str, Optional[int], Optional[int]]] = []
```
- **Purpose**: Initialize list to store alignment operations
- **Why**: Will hold the complete alignment path

```python
    i, j = n, m
```
- **Purpose**: Start backtracking from final cell
- **Why**: Reconstructs path from end to beginning

```python
    while not (i == 0 and j == 0):
```
- **Purpose**: Continue until reaching start (empty sequences)
- **Why**: Backtracks through entire alignment

```python
        op, ri, hj = back[i][j]
```
- **Purpose**: Get operation and indices from backtrack table
- **Why**: Retrieves the optimal operation for current position

```python
        ops.append((op, ri, hj))  # type: ignore[arg-type]
```
- **Purpose**: Add operation to path
- **Why**: Builds alignment sequence

```python
        if op in ("match", "sub"):
            i -= 1
            j -= 1
```
- **Purpose**: Move diagonally for match/substitution
- **Why**: Both sequences advance one position

```python
        elif op == "del":
            i -= 1
```
- **Purpose**: Move up for deletion
- **Why**: Only reference advances (word was deleted)

```python
        elif op == "ins":
            j -= 1
```
- **Purpose**: Move left for insertion
- **Why**: Only hypothesis advances (word was inserted)

```python
        else:
            break
```
- **Purpose**: Safety break for unknown operations
- **Why**: Prevents infinite loops

```python
    ops.reverse()
```
- **Purpose**: Reverse operations list to get forward order
- **Why**: Backtracking produces reverse order

```python
    return ops
```
- **Purpose**: Return alignment operations
- **Why**: Provides complete alignment path

---

### Lines 85-109: Reference-to-ASR Alignment

```python
def align_reference_to_asr(
    reference_text: str, asr_words: List[Dict[str, Any]]
) -> List[AlignedWord]:
```
- **Purpose**: Align reference text to ASR word list with timestamps
- **Parameters**: `reference_text` = expected text, `asr_words` = ASR output with timestamps
- **Returns**: List of AlignedWord objects

```python
    """
    Align reference tokens to ASR word list (each item like {start,end,word}).
    """
```
- **Purpose**: Docstring explaining function
- **Why**: Documents expected input format

```python
    ref_tokens = tokenize_reference(reference_text)
```
- **Purpose**: Convert reference text to normalized tokens
- **Why**: Prepares reference for alignment

```python
    hyp_tokens = [_normalize_token(w.get("word", "")) for w in asr_words if _normalize_token(w.get("word", ""))]
```
- **Purpose**: Extract and normalize words from ASR output
- **List comprehension**: Gets word from each ASR entry, normalizes, filters empty
- **Why**: Prepares hypothesis for alignment

```python
    # Map hyp token index to original asr_words entry with timestamps.
```
- **Purpose**: Comment explaining next section
- **Why**: Documents timestamp preservation

```python
    hyp_entries: List[Dict[str, Any]] = []
```
- **Purpose**: List to store original ASR entries with timestamps
- **Why**: Preserves timestamp information for aligned words

```python
    for w in asr_words:
        t = _normalize_token(w.get("word", ""))
        if t:
            hyp_entries.append(w)
```
- **Purpose**: Build list of valid ASR entries (non-empty after normalization)
- **Why**: Maintains correspondence between tokens and timestamp data

```python
    ops = _align_sequences(ref_tokens, hyp_tokens)
```
- **Purpose**: Run sequence alignment algorithm
- **Why**: Gets optimal alignment operations

```python
    aligned: List[AlignedWord] = []
```
- **Purpose**: Initialize list for aligned word pairs
- **Why**: Will store final alignment results

```python
    for op, ri, hj in ops:
```
- **Purpose**: Process each alignment operation
- **Why**: Converts operations to AlignedWord objects

```python
        ref_word = ref_tokens[ri] if ri is not None else None
```
- **Purpose**: Get reference word if operation involves reference
- **Why**: Handles insertions (no reference word)

```python
        hyp_word = hyp_tokens[hj] if hj is not None else None
```
- **Purpose**: Get hypothesis word if operation involves hypothesis
- **Why**: Handles deletions (no hypothesis word)

```python
        hyp_start = hyp_entries[hj].get("start") if hj is not None else None
```
- **Purpose**: Get start timestamp from original ASR entry
- **Why**: Preserves temporal information

```python
        hyp_end = hyp_entries[hj].get("end") if hj is not None else None
```
- **Purpose**: Get end timestamp from original ASR entry
- **Why**: Completes temporal boundaries

```python
        aligned.append(AlignedWord(ref_word=ref_word, hyp_word=hyp_word, op=op, hyp_start=hyp_start, hyp_end=hyp_end))
```
- **Purpose**: Create AlignedWord object and add to results
- **Why**: Stores complete alignment information

```python
    return aligned
```
- **Purpose**: Return complete alignment
- **Why**: Provides aligned word pairs with timestamps

---

### Lines 112-147: Main Word-Level Matcher Function

```python
def word_level_matcher(file_path: str, reference_text: str) -> List[Dict[str, Any]]:
```
- **Purpose**: Main function for content alignment
- **Parameters**: `file_path` = audio file, `reference_text` = expected text
- **Returns**: List of word results with status

```python
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
```
- **Purpose**: Docstring explaining function behavior
- **Why**: Documents output format and status meanings

```python
    asr = words_timestamps(file_path)
```
- **Purpose**: Get ASR word timestamps from audio
- **Why**: Gets what was actually spoken

```python
    aligned = align_reference_to_asr(reference_text, asr)
```
- **Purpose**: Align reference to ASR output
- **Why**: Finds correspondences between expected and spoken words

```python
    out: List[Dict[str, Any]] = []
```
- **Purpose**: Initialize output list
- **Why**: Will store final results

```python
    for a in aligned:
```
- **Purpose**: Process each aligned word pair
- **Why**: Converts alignment to status-based results

```python
        if a.op == "match":
            out.append({"word": a.ref_word, "status": "correct", "start": a.hyp_start, "end": a.hyp_end})
```
- **Purpose**: Handle matched words (correctly spoken)
- **Why**: Words that align perfectly are marked correct

```python
        elif a.op == "del":
            out.append({"word": a.ref_word, "status": "missed", "start": None, "end": None})
```
- **Purpose**: Handle deleted words (missed in speech)
- **Why**: Reference words not found in ASR are missed

```python
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
```
- **Purpose**: Handle substituted words (wrong word spoken)
- **Why**: Reference word replaced by different word in ASR

```python
        elif a.op == "ins":
            out.append({"word": a.hyp_word, "status": "repeated", "start": a.hyp_start, "end": a.hyp_end})
```
- **Purpose**: Handle inserted words (extra words spoken)
- **Why**: Words in ASR not in reference are repeated/extra

```python
    return out
```
- **Purpose**: Return final results
- **Why**: Provides content alignment results

---

### Lines 150-153: Main Block

```python
if __name__ == "__main__":
```
- **Purpose**: Code runs only when script is executed directly
- **Why**: Allows module to be imported without running test code

```python
    file_path = "input.wav"
```
- **Purpose**: Example audio file path
- **Why**: Test file for demonstration

```python
    reference_text = "bicycle racing is the"
```
- **Purpose**: Example reference text
- **Why**: Test reference for demonstration

```python
    print(word_level_matcher(file_path, reference_text))
```
- **Purpose**: Run function and print results
- **Why**: Demonstrates usage and tests functionality

---

## Summary

This module implements the **content accuracy** part of the PTE system:
1. **Normalizes** text for fair comparison
2. **Aligns** reference and ASR sequences using edit distance
3. **Categorizes** words as correct, missed, substituted, or repeated
4. **Preserves** timestamps for aligned words

The key insight: **Content errors come from sequence alignment, not pronunciation assessment.**
