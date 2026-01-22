"""Word-level matching and scoring for PTE Read Aloud."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..alignment.aligner import align_reference_to_asr
from ..alignment.normalizer import is_punctuation
from ..asr.lazy_loader import get_words_timestamps
from ..pause.pause_evaluator import evaluate_pause
from ..pause.speech_rate import calculate_speech_rate_scale
from ..pause.hesitation import apply_hesitation_clustering
from ..pause.rules import PAUSE_PUNCTUATION


def word_level_matcher(file_path: str, reference_text: str) -> List[Dict[str, Any]]:
    """Core content-alignment output used by the rest of the system.

    Returns list of dicts:
      - For ref words: {word, status, start, end}
      - For punctuation: {word, status, penalty, pause_duration, expected_range, start, end}
      
      Word status in {"correct","missed","substituted","repeated"}
      Punctuation status in {"correct_pause","short_pause","long_pause","missed_pause"}
      Penalty: 0.0-1.0 numeric score (0.0=perfect, 1.0=worst) for fluency scoring

    Notes:
      - "missed" comes from deletions (ref token not spoken)
      - "repeated" comes from insertions (extra spoken token)
      - "substituted" comes from substitutions
      - Pause detection checks gap between words when punctuation is not in ASR output
      
    Args:
        file_path: Path to audio file (currently unused, reserved for future ASR integration)
        reference_text: The reference text to match against
        
    Returns:
        List of dictionaries with word/punctuation matching results
    """
    asr = get_words_timestamps()
    aligned = align_reference_to_asr(reference_text, asr)

    # Calculate speech rate scaling for adaptive thresholds
    speech_rate_scale = calculate_speech_rate_scale(asr)

    out: List[Dict[str, Any]] = []
    
    # Track the last word's end timestamp and previous word for pause detection
    last_word_end: Optional[float] = None
    prev_word: Optional[str] = None
    
    for idx, a in enumerate(aligned):
        # Check if this is a punctuation token
        if a.ref_word and is_punctuation(a.ref_word):
            # This is a punctuation mark - need to evaluate pause
            # Always infer pause from word gaps (ASR punctuation timestamps are unreliable)
            next_start = None
            # Find the next non-punctuation aligned word to get its start time
            for future_a in aligned[idx + 1:]:
                if future_a.hyp_start is not None:
                    next_start = future_a.hyp_start
                    break
            
            pause_duration = None
            if last_word_end is not None and next_start is not None:
                # Clamp to prevent negative durations from overlapping timestamps
                pause_duration = max(0.0, next_start - last_word_end)
            
            # Check if previous word was repeated (for PTE-specific penalty)
            # Look back to find the last spoken word and check if it was an insertion (repetition)
            is_after_repeated = False
            for back_idx in range(idx - 1, -1, -1):
                back_a = aligned[back_idx]
                if back_a.ref_word and not is_punctuation(back_a.ref_word):
                    # If the last spoken word was an insertion, it's likely a repetition
                    if back_a.op == "ins":
                        is_after_repeated = True
                    break
            
            result = evaluate_pause(
                a.ref_word, pause_duration, last_word_end, next_start,
                speech_rate_scale=speech_rate_scale,
                prev_word=prev_word,
                is_after_repeated=is_after_repeated
            )
            out.append(result)
        else:
            # Regular word processing
            if a.op == "match":
                out.append({"word": a.ref_word, "status": "correct", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
                prev_word = a.ref_word  # Update previous word
            elif a.op == "del":
                out.append({"word": a.ref_word, "status": "missed", "start": None, "end": None})
                # DO NOT update prev_word - word was not spoken, so it shouldn't affect pause rules
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
                prev_word = a.ref_word  # Use reference word for context
            elif a.op == "ins":
                out.append({"word": a.hyp_word, "status": "repeated", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
                prev_word = a.hyp_word  # Use hypothesis word for context
    
    # Apply hesitation clustering to pause results
    # Add stable pause_id to each pause result before clustering
    pause_counter = 0
    for result in out:
        if result.get("word") in PAUSE_PUNCTUATION:
            result["pause_id"] = pause_counter
            pause_counter += 1
    
    pause_indices = [i for i, r in enumerate(out) if r.get("word") in PAUSE_PUNCTUATION]
    pause_results = [out[i] for i in pause_indices]
    if pause_results:
        clustered_pauses = apply_hesitation_clustering(pause_results)
        # Match by pause_id instead of index for stability
        pause_id_map = {r.get("pause_id"): r for r in clustered_pauses}
        for result in out:
            if "pause_id" in result:
                clustered = pause_id_map.get(result["pause_id"])
                if clustered:
                    result["penalty"] = clustered.get("penalty", result.get("penalty", 0.0))
                    if "cluster_size" in clustered:
                        result["cluster_size"] = clustered["cluster_size"]

    return out


def word_level_matcher_from_asr(asr_words: List[Dict[str, Any]], reference_text: str) -> List[Dict[str, Any]]:
    """Same as word_level_matcher but accepts ASR words directly instead of file path.
    
    Useful for testing without loading the ASR model.
    
    Args:
        asr_words: List of ASR word entries with timestamps
        reference_text: The reference text to match against
        
    Returns:
        List of dictionaries with word/punctuation matching results
    """
    aligned = align_reference_to_asr(reference_text, asr_words)

    # Calculate speech rate scaling for adaptive thresholds
    speech_rate_scale = calculate_speech_rate_scale(asr_words)

    out: List[Dict[str, Any]] = []
    last_word_end: Optional[float] = None
    prev_word: Optional[str] = None
    
    for idx, a in enumerate(aligned):
        if a.ref_word and is_punctuation(a.ref_word):
            # Always infer pause from word gaps (ASR punctuation timestamps are unreliable)
            next_start = None
            for future_a in aligned[idx + 1:]:
                if future_a.hyp_start is not None:
                    next_start = future_a.hyp_start
                    break
            
            pause_duration = None
            if last_word_end is not None and next_start is not None:
                # Clamp to prevent negative durations from overlapping timestamps
                pause_duration = max(0.0, next_start - last_word_end)
            
            # Check if previous word was repeated (for PTE-specific penalty)
            # Look back to find the last spoken word and check if it was an insertion (repetition)
            is_after_repeated = False
            for back_idx in range(idx - 1, -1, -1):
                back_a = aligned[back_idx]
                if back_a.ref_word and not is_punctuation(back_a.ref_word):
                    # If the last spoken word was an insertion, it's likely a repetition
                    if back_a.op == "ins":
                        is_after_repeated = True
                    break
            
            result = evaluate_pause(
                a.ref_word, pause_duration, last_word_end, next_start,
                speech_rate_scale=speech_rate_scale,
                prev_word=prev_word,
                is_after_repeated=is_after_repeated
            )
            out.append(result)
        else:
            if a.op == "match":
                out.append({"word": a.ref_word, "status": "correct", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
                prev_word = a.ref_word
            elif a.op == "del":
                out.append({"word": a.ref_word, "status": "missed", "start": None, "end": None})
                # DO NOT update prev_word - word was not spoken, so it shouldn't affect pause rules
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
                prev_word = a.ref_word
            elif a.op == "ins":
                out.append({"word": a.hyp_word, "status": "repeated", "start": a.hyp_start, "end": a.hyp_end})
                if a.hyp_end is not None:
                    last_word_end = a.hyp_end
                prev_word = a.hyp_word
    
    # Apply hesitation clustering to pause results
    # Add stable pause_id to each pause result before clustering
    pause_counter = 0
    for result in out:
        if result.get("word") in PAUSE_PUNCTUATION:
            result["pause_id"] = pause_counter
            pause_counter += 1
    
    pause_indices = [i for i, r in enumerate(out) if r.get("word") in PAUSE_PUNCTUATION]
    pause_results = [out[i] for i in pause_indices]
    if pause_results:
        clustered_pauses = apply_hesitation_clustering(pause_results)
        # Match by pause_id instead of index for stability
        pause_id_map = {r.get("pause_id"): r for r in clustered_pauses}
        for result in out:
            if "pause_id" in result:
                clustered = pause_id_map.get(result["pause_id"])
                if clustered:
                    result["penalty"] = clustered.get("penalty", result.get("penalty", 0.0))
                    if "cluster_size" in clustered:
                        result["cluster_size"] = clustered["cluster_size"]

    return out
