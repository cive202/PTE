from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING
# Lazy import to avoid loading the model at module level
if TYPE_CHECKING:
    pass  # For type hints only


def _get_words_timestamps() -> List[Dict[str, Any]]:
    """Lazy import wrapper for words_timestamps to avoid loading model at import time."""
    # 
    # from voice2text import words_timestamps
    from pseudo_voice2text import voice2text_word
    return voice2text_word()

def _get_char_timestamps() -> List[Dict[str, Any]]:
    """Lazy import wrapper for voice2text_char to avoid loading model at import time."""
    # 
    # from voice2text import words_timestamps
    from pseudo_voice2text import voice2text_char
    return voice2text_char()

def _get_segment_timestamps() -> List[Dict[str, Any]]:
    """Lazy import wrapper for voice2text_segment to avoid loading model at import time."""
    # 
    # from voice2text import words_timestamps
    from pseudo_voice2text import  voice2text_segment
    return voice2text_segment()


# Punctuation that requires pauses (for PTE scoring)
PAUSE_PUNCTUATION = {",", "."}

# Pause thresholds in seconds: (min_pause, max_pause)
PAUSE_THRESHOLDS = {
    ",": (0.3, 0.5),   # Comma: 0.3s to 0.5s
    ".": (0.6, 1.0),   # Period: 0.6s to 1.0s
}

    
def _is_punctuation(token: str) -> bool:
    """Check if token is a pause-worthy punctuation mark."""
    return token in PAUSE_PUNCTUATION


def _normalize_token(token: str, preserve_punctuation: bool = True) -> str:
    """
    Normalize a token for alignment.
    
    If preserve_punctuation is True, punctuation marks (,.) are preserved as-is.
    Otherwise, all punctuation is stripped.
    """
    token = token.lower().strip()
    
    # If it's a standalone punctuation mark, preserve it
    if preserve_punctuation and token in PAUSE_PUNCTUATION:
        return token
    
    # keep apostrophes inside words, drop other punctuation
    token = re.sub(r"[^a-z0-9']+", "", token)
    return token


def tokenize_reference(text: str) -> List[str]:
    """
    Tokenize reference text, separating punctuation marks as individual tokens.
    
    Example: "Hello, world." -> ["hello", ",", "world", "."]
    """
    tokens = []
    # Split on whitespace first
    raw = re.split(r"\s+", text.strip())
    
    for word in raw:
        if not word:
            continue
        
        # Collect trailing punctuation
        trailing_punct = []
        while word and word[-1] in PAUSE_PUNCTUATION:
            trailing_punct.append(word[-1])
            word = word[:-1]
        
        # Add the word part (if any)
        if word:
            normalized = _normalize_token(word)
            if normalized:
                tokens.append(normalized)
        
        # Add trailing punctuation in order (reverse since we collected from end)
        for punct in reversed(trailing_punct):
            tokens.append(punct)
    
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


def _tokenize_asr(asr_words: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Tokenize ASR output, preserving punctuation as separate tokens.
    
    Returns:
        - hyp_tokens: List of normalized tokens (words and punctuation)
        - hyp_entries: List of corresponding ASR entries with timestamps
    """
    hyp_tokens: List[str] = []
    hyp_entries: List[Dict[str, Any]] = []
    
    for w in asr_words:
        raw_word = w.get("word", "")
        normalized = _normalize_token(raw_word)
        if normalized:
            hyp_tokens.append(normalized)
            hyp_entries.append(w)
    
    return hyp_tokens, hyp_entries


def align_reference_to_asr(
    reference_text: str, asr_words: List[Dict[str, Any]]
) -> List[AlignedWord]:
    """
    Align reference tokens to ASR word list (each item like {start,end,word}).
    Now includes punctuation tokens for pause detection.
    """
    ref_tokens = tokenize_reference(reference_text)
    hyp_tokens, hyp_entries = _tokenize_asr(asr_words)

    ops = _align_sequences(ref_tokens, hyp_tokens)
    aligned: List[AlignedWord] = []
    for op, ri, hj in ops:
        ref_word = ref_tokens[ri] if ri is not None else None
        hyp_word = hyp_tokens[hj] if hj is not None else None
        hyp_start = hyp_entries[hj].get("start") if hj is not None else None
        hyp_end = hyp_entries[hj].get("end") if hj is not None else None
        aligned.append(AlignedWord(ref_word=ref_word, hyp_word=hyp_word, op=op, hyp_start=hyp_start, hyp_end=hyp_end))
    return aligned


def _evaluate_pause(
    punct: str,
    pause_duration: Optional[float],
    prev_end: Optional[float],
    next_start: Optional[float]
) -> Dict[str, Any]:
    """
    Evaluate pause at a punctuation mark.
    
    Returns a dict with pause status and details.
    """
    min_pause, max_pause = PAUSE_THRESHOLDS.get(punct, (0.3, 0.5))
    
    result = {
        "word": punct,
        "expected_range": (min_pause, max_pause),
        "start": prev_end,
        "end": next_start,
    }
    
    if pause_duration is None:
        result["status"] = "missed_pause"
        result["pause_duration"] = None
    elif pause_duration < min_pause:
        result["status"] = "short_pause"
        result["pause_duration"] = pause_duration
    elif pause_duration > max_pause:
        result["status"] = "long_pause"
        result["pause_duration"] = pause_duration
    else:
        result["status"] = "correct_pause"
        result["pause_duration"] = pause_duration
    
    return result


def word_level_matcher(file_path: str, reference_text: str) -> List[Dict[str, Any]]:
    """
    Core content-alignment output used by the rest of the system.

    Returns list of dicts:
      - For ref words: {word, status, start, end}
      - For punctuation: {word, status, pause_duration, expected_range, start, end}
      
      Word status in {"correct","missed","substituted","repeated"}
      Punctuation status in {"correct_pause","short_pause","long_pause","missed_pause"}

    Notes:
      - "missed" comes from deletions (ref token not spoken)
      - "repeated" comes from insertions (extra spoken token)
      - "substituted" comes from substitutions
      - Pause detection checks gap between words when punctuation is not in ASR output
    """
    asr = words_timestamps(file_path)
    aligned = align_reference_to_asr(reference_text, asr)

    out: List[Dict[str, Any]] = []
    
    # Track the last word's end timestamp for pause detection
    last_word_end: Optional[float] = None
    
    for idx, a in enumerate(aligned):
        # Check if this is a punctuation token
        if a.ref_word and _is_punctuation(a.ref_word):
            # This is a punctuation mark - need to evaluate pause
            if a.op == "match":
                # ASR also output this punctuation - use its timestamps
                # Calculate pause as gap before punctuation or use ASR timing
                pause_duration = None
                if last_word_end is not None and a.hyp_start is not None:
                    pause_duration = a.hyp_start - last_word_end
                elif a.hyp_start is not None and a.hyp_end is not None:
                    # Use punctuation token duration as approximation
                    pause_duration = a.hyp_end - a.hyp_start
                
                result = _evaluate_pause(a.ref_word, pause_duration, last_word_end, a.hyp_start)
                out.append(result)
                
                # Update last_word_end to after the punctuation
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
            else:
                # Punctuation not in ASR output (del) or mismatched (sub)
                # Look for pause by checking gap to next word
                next_start = None
                # Find the next non-punctuation aligned word to get its start time
                for future_a in aligned[idx + 1:]:
                    if future_a.hyp_start is not None:
                        next_start = future_a.hyp_start
                        break
                
                pause_duration = None
                if last_word_end is not None and next_start is not None:
                    pause_duration = next_start - last_word_end
                
                result = _evaluate_pause(a.ref_word, pause_duration, last_word_end, next_start)
                out.append(result)
        else:
            # Regular word processing
            if a.op == "match":
                out.append({"word": a.ref_word, "status": "correct", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
            elif a.op == "del":
                out.append({"word": a.ref_word, "status": "missed", "start": None, "end": None})
                # Don't update last_word_end for missed words
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
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
            elif a.op == "ins":
                out.append({"word": a.hyp_word, "status": "repeated", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end

    return out


def word_level_matcher_from_asr(asr_words: List[Dict[str, Any]], reference_text: str) -> List[Dict[str, Any]]:
    """
    Same as word_level_matcher but accepts ASR words directly instead of file path.
    Useful for testing without loading the ASR model.
    """
    aligned = align_reference_to_asr(reference_text, asr_words)

    out: List[Dict[str, Any]] = []
    last_word_end: Optional[float] = None
    
    for idx, a in enumerate(aligned):
        if a.ref_word and _is_punctuation(a.ref_word):
            if a.op == "match":
                pause_duration = None
                if last_word_end is not None and a.hyp_start is not None:
                    pause_duration = a.hyp_start - last_word_end
                elif a.hyp_start is not None and a.hyp_end is not None:
                    pause_duration = a.hyp_end - a.hyp_start
                
                result = _evaluate_pause(a.ref_word, pause_duration, last_word_end, a.hyp_start)
                out.append(result)
                
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
            else:
                next_start = None
                for future_a in aligned[idx + 1:]:
                    if future_a.hyp_start is not None:
                        next_start = future_a.hyp_start
                        break
                
                pause_duration = None
                if last_word_end is not None and next_start is not None:
                    pause_duration = next_start - last_word_end
                
                result = _evaluate_pause(a.ref_word, pause_duration, last_word_end, next_start)
                out.append(result)
        else:
            if a.op == "match":
                out.append({"word": a.ref_word, "status": "correct", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
            elif a.op == "del":
                out.append({"word": a.ref_word, "status": "missed", "start": None, "end": None})
            elif a.op == "sub":
                out.append({
                    "word": a.ref_word,
                    "status": "substituted",
                    "start": a.hyp_start,
                    "end": a.hyp_end,
                    "spoken": a.hyp_word,
                })
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
            elif a.op == "ins":
                out.append({"word": a.hyp_word, "status": "repeated", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end

    return out


def parse_transcript(transcript: str) -> List[Dict[str, Any]]:
    """
    Parse a transcript in format: 'start_time - end_time : text'
    Returns list of word-level entries with estimated timestamps.
    """
    import re
    asr_words = []
    
    for line in transcript.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Parse format: "0.24s - 2.4s : Tell me about Christmas"
        match = re.match(r'([\d.]+)s?\s*-\s*([\d.]+)s?\s*:\s*(.+)', line)
        if match:
            start = float(match.group(1))
            end = float(match.group(2))
            text = match.group(3).strip()
            
            # Split text into words and distribute timestamps
            words = text.split()
            if words:
                duration = end - start
                word_duration = duration / len(words)
                
                for i, word in enumerate(words):
                    word_start = start + (i * word_duration)
                    word_end = start + ((i + 1) * word_duration)
                    asr_words.append({
                        "word": word,
                        "start": round(word_start, 3),
                        "end": round(word_end, 3)
                    })
    
    return asr_words


if __name__ == "__main__":
    # Real transcript data (ASR output with timestamps)
    transcript = """
0.24s - 2.4s : Tell me about Christmas and New Year.
3.36s - 4.96s : What did you get up to?
5.92s - 17.76s : I was working quite a lot during the Christmas and New Year, eating and I did quite a lot of cooking and helping in my parents' restaurant.
19.52s - 25.36s : Okay, what uh what sort of stuff were you cooking described how you were doing and how you were doing it?
25.68s - 29.44s : I was cooking carp was the Czechs, that Czech tradition.
29.76s - 30.32s : Coffee?
30.72s - 31.12s : Yes.
31.44s - 32.4s : As in a fish.
32.64s - 33.04s : Yes.  
34.32s - 37.36s : Bread crumbed and then pan fried.
38.24s - 43.84s : It's served with potato salad and Czech lager.
45.44s - 46.48s : Czech vaga?
46.64s - 46.80s : Yes.
47.2s - 48.4s : Hungarian vaga.
49.2s - 49.52s : No.
50.16s - 50.48s : Okax`y.
50.80s - 54.0s : Um were you cooking anything else?
56.88s - 57.12s : No.
58.08s - 58.24s : Okay.
58.88s - 63.12s : Um tell me about what you did on Christmas Day.
64.08s - 70.64s : Well, I slept till about 2:30 in the afternoon, so I didn't really have much of the day.
71.84s - 77.68s : Right, but then you've surely got up and had Christmas meal and stuff.
78.24s - 81.04s : I had that on the 24th in the evening.
81.36s - 82.24s : Alright, yes.
82.56s - 82.96s : Why is that?
83.04s - 85.84s : Is that Hungarian tradition or Czech tradition?
86.72s - 88.24s : I'm sorry, I thought you were Hungarian.
88.48s - 89.92s : No, I'm not Hungarian, I'm afraid.
90.8s - 92.08s : Oh no, that's really bad.
92.16s - 92.8s : I'm very sorry.
93.2s - 93.60s : That's okay.
"""

    print("=== Parsing Transcript (ASR Output) ===")
    asr_words = parse_transcript(transcript)
    print(f"Total words parsed: {len(asr_words)}")
    
    # Full reference text for PTE Read Aloud
    reference_text = """I was working quite a lot during Christmas and New Year, eating and doing a lot of cooking while helping in my parents' restaurant. I was cooking carp, which is a Czech tradition. It is breadcrumbed and then pan-fried, and it is usually served with potato salad and Czech lager. I was not cooking anything else. On Christmas Day, I slept until about 2:30 in the afternoon, so I did not really have much of the day. We actually had our Christmas meal on the 24th in the evening, which is a Czech tradition, and although there was some confusion about whether it was Hungarian or Czech, it was confirmed to be Czech in the end."""
    
    print("\n=== Reference Text ===")
    print(reference_text)
    
    print("\n=== Tokenized Reference ===")
    tokens = tokenize_reference(reference_text)
    print(f"Total tokens: {len(tokens)}")
    punct_count = sum(1 for t in tokens if _is_punctuation(t))
    print(f"Punctuation marks: {punct_count}")
    print(f"Tokens: {tokens}")
    
    print("\n=== Word Level Matching Results ===")
    result = word_level_matcher_from_asr(asr_words, reference_text)
    
    # Summarize results
    correct = [r for r in result if r.get('status') == 'correct']
    missed = [r for r in result if r.get('status') == 'missed']
    substituted = [r for r in result if r.get('status') == 'substituted']
    repeated = [r for r in result if r.get('status') == 'repeated']
    
    correct_pause = [r for r in result if r.get('status') == 'correct_pause']
    short_pause = [r for r in result if r.get('status') == 'short_pause']
    long_pause = [r for r in result if r.get('status') == 'long_pause']
    missed_pause = [r for r in result if r.get('status') == 'missed_pause']
    
    print(f"\n--- Word Statistics ---")
    print(f"Correct words: {len(correct)}")
    print(f"Missed words: {len(missed)}")
    print(f"Substituted words: {len(substituted)}")
    print(f"Repeated/Extra words: {len(repeated)}")
    
    print(f"\n--- Pause Statistics ---")
    print(f"Correct pauses: {len(correct_pause)}")
    print(f"Short pauses: {len(short_pause)}")
    print(f"Long pauses: {len(long_pause)}")
    print(f"Missed pauses: {len(missed_pause)}")
    
    print(f"\n--- Detailed Pause Results ---")
    for r in result:
        if r.get('word') in PAUSE_PUNCTUATION:
            print(f"  {r}")
    
    print(f"\n--- All Results (first 50) ---")
    for i, r in enumerate(result[:50]):
        print(f"  {i}: {r}")
