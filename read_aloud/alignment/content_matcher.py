"""Reference-conditioned content matching for read-aloud transcripts."""
from __future__ import annotations

from typing import List, Tuple

from .edit_distance import align_sequences
from .normalizer import is_punctuation
from .tokenizer import tokenize_reference, tokenize_transcript


def compare_text(reference_text: str, transcription: str) -> Tuple[List[dict], str]:
    """Compare reference text with a transcript for read-aloud content matching.

    Design goals:
    - preserve punctuation tokens from the reference for later pause scoring
    - ignore transcript punctuation as lexical evidence
    - normalize hyphen variants like ``time-saving`` -> ``time saving``
    - never emit empty inserted tokens
    """
    ref_tokens = tokenize_reference(reference_text)
    transcript_tokens = tokenize_transcript(transcription)
    ref_lexical_positions = [
        (full_index, token)
        for full_index, token in enumerate(ref_tokens)
        if not is_punctuation(token)
    ]
    ref_lexical_tokens = [token for _, token in ref_lexical_positions]
    ops = align_sequences(ref_lexical_tokens, transcript_tokens)
    diff_results: List[dict] = []

    last_full_index = -1

    def flush_reference_gap(target_full_index: int) -> None:
        nonlocal last_full_index
        for full_index in range(last_full_index + 1, target_full_index):
            token = ref_tokens[full_index]
            if is_punctuation(token):
                diff_results.append(
                    {
                        "word": token,
                        "status": "omitted",
                        "ref_index": full_index,
                        "trans_index": None,
                        "alignment_op": "punct",
                        "content_support": "punctuation",
                    }
                )
        last_full_index = target_full_index - 1

    for op, ref_lex_index, trans_index in ops:
        if ref_lex_index is None:
            diff_results.append(
                {
                    "word": transcript_tokens[trans_index],
                    "status": "inserted",
                    "ref_index": None,
                    "trans_index": trans_index,
                    "alignment_op": "ins",
                    "content_support": "inserted",
                    "asr_word": transcript_tokens[trans_index],
                }
            )
            continue

        full_ref_index, ref_token = ref_lexical_positions[ref_lex_index]
        flush_reference_gap(full_ref_index)

        if op == "match":
            diff_results.append(
                {
                    "word": ref_token,
                    "status": "correct",
                    "ref_index": full_ref_index,
                    "trans_index": trans_index,
                    "alignment_op": "match",
                    "content_support": "match",
                    "asr_word": transcript_tokens[trans_index],
                }
            )
        elif op == "sub":
            diff_results.append(
                {
                    "word": ref_token,
                    "status": "correct",
                    "ref_index": full_ref_index,
                    "trans_index": trans_index,
                    "alignment_op": "sub",
                    "content_support": "contradicted",
                    "asr_word": transcript_tokens[trans_index],
                }
            )
            diff_results.append(
                {
                    "word": transcript_tokens[trans_index],
                    "status": "inserted",
                    "ref_index": None,
                    "trans_index": trans_index,
                    "alignment_op": "sub_ins",
                    "content_support": "inserted",
                    "asr_word": transcript_tokens[trans_index],
                    "anchor_ref_index": full_ref_index,
                }
            )
        elif op == "del":
            diff_results.append(
                {
                    "word": ref_token,
                    "status": "correct",
                    "ref_index": full_ref_index,
                    "trans_index": None,
                    "alignment_op": "del",
                    "content_support": "unsupported",
                    "asr_word": None,
                }
            )
        else:
            raise ValueError(f"Unsupported alignment op: {op}")

        last_full_index = full_ref_index

    flush_reference_gap(len(ref_tokens))

    return diff_results, " ".join(transcript_tokens)
