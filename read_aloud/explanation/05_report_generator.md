# Line-by-Line Explanation: report_generator.py

## Overview
This module merges content alignment results (from word-level matching) with pronunciation assessment results (from MFA or WavLM) to generate a unified word-level report.

---

## Line-by-Line Breakdown

### Lines 1-4: Imports

```python
from __future__ import annotations
```
- **Purpose**: Enables forward references in type hints
- **Why**: Allows using types before definition

```python
from typing import Any, Dict, List, Optional
```
- **Purpose**: Import type hints
- **Why**: Type annotations for documentation

---

### Lines 6-114: Content and Pronunciation Merger

```python
def merge_content_and_pronunciation(
    content_results: List[Dict[str, Any]],
    pronunciation_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
```
- **Purpose**: Merge content alignment with pronunciation assessment
- **Parameters**:
  - `content_results`: Results from word_level_matcher (content errors)
  - `pronunciation_results`: Results from MFA/WavLM (pronunciation errors)
- **Returns**: Unified word-level report

```python
    """
    Merge content alignment results with pronunciation assessment.
    
    Content results come from word_level_matcher (status: correct, missed, substituted, repeated).
    Pronunciation results come from MFA or WavLM (status: correct, mispronounced).
    
    Decision rules:
    - MISSED: word in reference but not in ASR → status="missed"
    - REPEATED: extra word in ASR → status="repeated"
    - MISPRONOUNCED: word aligned but pronunciation confidence < threshold → status="mispronounced"
    - CORRECT: word aligned and pronunciation confidence >= threshold → status="correct"
    
    Args:
        content_results: List from word_level_matcher with {word, status, start, end, ...}
        pronunciation_results: List from MFA/WavLM with {word, start, end, confidence, status}
    
    Returns:
        Unified report: List of {word, status, start, end, confidence}
    """
```
- **Purpose**: Comprehensive docstring explaining merge logic
- **Why**: Documents decision rules and data flow

```python
    # Create lookup: word -> pronunciation result
    # Match by word text (normalized)
    pron_dict: Dict[str, Dict[str, Any]] = {}
```
- **Purpose**: Initialize dictionary for pronunciation lookup
- **Why**: Fast lookup by word text

```python
    for pron in pronunciation_results:
        word_key = pron.get("word", "").lower().strip()
        if word_key:
            pron_dict[word_key] = pron
```
- **Purpose**: Build pronunciation lookup dictionary
- **Process**: Normalize word (lowercase, strip) as key
- **Why**: Enables fast matching between content and pronunciation results

```python
    unified: List[Dict[str, Any]] = []
```
- **Purpose**: Initialize unified results list
- **Why**: Will store merged results

```python
    for content in content_results:
```
- **Purpose**: Process each content alignment result
- **Why**: Merges content errors with pronunciation assessment

```python
        word = content.get("word", "")
        content_status = content.get("status", "")
```
- **Purpose**: Extract word and status from content result
- **Why**: Gets content-level information

```python
        # Content-level errors take precedence
        if content_status == "missed":
```
- **Purpose**: Handle missed words (content error)
- **Why**: Content errors override pronunciation assessment

```python
            unified.append(
                {
                    "word": word,
                    "status": "missed",
                    "start": None,
                    "end": None,
                    "confidence": 0.0,
                }
            )
```
- **Purpose**: Add missed word to results
- **Why**: Word wasn't spoken, so no timestamps or confidence
- **Status**: "missed" (content error)

```python
        elif content_status == "repeated":
```
- **Purpose**: Handle repeated/extra words (content error)
- **Why**: Word was spoken but not in reference

```python
            unified.append(
                {
                    "word": word,
                    "status": "repeated",
                    "start": content.get("start"),
                    "end": content.get("end"),
                    "confidence": 0.0,
                }
            )
```
- **Purpose**: Add repeated word to results
- **Why**: Word was spoken (has timestamps) but is extra
- **Status**: "repeated" (content error)

```python
        elif content_status == "substituted":
```
- **Purpose**: Handle substituted words (content error)
- **Why**: Wrong word was spoken

```python
            # Substituted words are content errors
            unified.append(
                {
                    "word": word,
                    "status": "substituted",
                    "start": content.get("start"),
                    "end": content.get("end"),
                    "confidence": 0.0,
                    "spoken": content.get("spoken"),
                }
            )
```
- **Purpose**: Add substituted word to results
- **Why**: Reference word replaced by different word
- **`spoken`**: What was actually said (for reference)

```python
        elif content_status == "correct":
```
- **Purpose**: Handle correctly aligned words
- **Why**: Word was spoken correctly, now check pronunciation

```python
            # Word was aligned correctly - check pronunciation
            word_key = word.lower().strip()
            pron_result = pron_dict.get(word_key)
```
- **Purpose**: Look up pronunciation assessment for this word
- **Why**: Checks if pronunciation was assessed

```python
            if pron_result:
```
- **Purpose**: Check if pronunciation result exists
- **Why**: Word may not have pronunciation assessment

```python
                # Use pronunciation assessment
                pron_status = pron_result.get("status", "mispronounced")
                confidence = pron_result.get("confidence", 0.0)
```
- **Purpose**: Extract pronunciation status and confidence
- **Why**: Gets pronunciation quality information

```python
                # Use timestamps from content (ASR) if available, otherwise from pronunciation
                start = content.get("start") or pron_result.get("start")
                end = content.get("end") or pron_result.get("end")
```
- **Purpose**: Prefer ASR timestamps, fallback to pronunciation timestamps
- **Why**: ASR timestamps are usually more accurate

```python
                unified.append(
                    {
                        "word": word,
                        "status": pron_status,  # "correct" or "mispronounced"
                        "start": start,
                        "end": end,
                        "confidence": confidence,
                    }
                )
```
- **Purpose**: Add word with pronunciation assessment
- **Why**: Word aligned correctly, status depends on pronunciation
- **Status**: "correct" or "mispronounced" (from pronunciation assessment)

```python
            else:
```
- **Purpose**: Handle case where no pronunciation result exists
- **Why**: Pronunciation assessment may not cover all words

```python
                # Word aligned but no pronunciation result - default to correct
                unified.append(
                    {
                        "word": word,
                        "status": "correct",
                        "start": content.get("start"),
                        "end": content.get("end"),
                        "confidence": 1.0,  # Default confidence
                    }
                )
```
- **Purpose**: Default to correct if no pronunciation assessment
- **Why**: Assumes correct pronunciation if not assessed
- **Confidence**: Defaults to 1.0 (perfect)

```python
        else:
            # Unknown status - include as-is
            unified.append(content)
```
- **Purpose**: Handle unknown statuses
- **Why**: Safety fallback for unexpected statuses

```python
    return unified
```
- **Purpose**: Return unified results
- **Why**: Provides complete word-level report

---

### Lines 117-162: Final Report Generator

```python
def generate_final_report(
    content_results: List[Dict[str, Any]],
    pronunciation_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
```
- **Purpose**: Generate final report with statistics
- **Parameters**: Same as merge function
- **Returns**: Dict with 'words' list and 'summary' dict

```python
    """
    Generate final unified report with statistics.
    
    Args:
        content_results: Content alignment results
        pronunciation_results: Pronunciation assessment results
    
    Returns:
        Dict with 'words' (list) and 'summary' (stats dict)
    """
```
- **Purpose**: Docstring
- **Why**: Documents function and return format

```python
    words = merge_content_and_pronunciation(content_results, pronunciation_results)
```
- **Purpose**: Merge content and pronunciation results
- **Why**: Gets unified word-level report

```python
    # Calculate statistics
    total_words = len(words)
```
- **Purpose**: Count total words
- **Why**: Needed for accuracy calculation

```python
    correct = sum(1 for w in words if w.get("status") == "correct")
```
- **Purpose**: Count correct words
- **Process**: Sum 1 for each word with status "correct"
- **Why**: Measures pronunciation accuracy

```python
    mispronounced = sum(1 for w in words if w.get("status") == "mispronounced")
```
- **Purpose**: Count mispronounced words
- **Why**: Measures pronunciation errors

```python
    missed = sum(1 for w in words if w.get("status") == "missed")
```
- **Purpose**: Count missed words
- **Why**: Measures content errors (not spoken)

```python
    repeated = sum(1 for w in words if w.get("status") == "repeated")
```
- **Purpose**: Count repeated/extra words
- **Why**: Measures content errors (extra words)

```python
    substituted = sum(1 for w in words if w.get("status") == "substituted")
```
- **Purpose**: Count substituted words
- **Why**: Measures content errors (wrong words)

```python
    # Average confidence for correctly pronounced words
    correct_confidences = [
        w.get("confidence", 0.0) for w in words if w.get("status") == "correct"
    ]
```
- **Purpose**: Extract confidence scores for correct words
- **Why**: Calculates average confidence

```python
    avg_confidence = (
        sum(correct_confidences) / len(correct_confidences)
        if correct_confidences
        else 0.0
    )
```
- **Purpose**: Calculate average confidence
- **Formula**: Sum / count
- **Why**: Measures pronunciation quality for correct words
- **Safety**: Returns 0.0 if no correct words

```python
    summary = {
        "total_words": total_words,
        "correct": correct,
        "mispronounced": mispronounced,
        "missed": missed,
        "repeated": repeated,
        "substituted": substituted,
        "accuracy": (correct / total_words * 100.0) if total_words > 0 else 0.0,
        "average_confidence": avg_confidence,
    }
```
- **Purpose**: Build summary statistics dictionary
- **Metrics**:
  - Counts for each status
  - Accuracy percentage (correct / total × 100)
  - Average confidence
- **Why**: Provides overall assessment metrics

```python
    return {"words": words, "summary": summary}
```
- **Purpose**: Return complete report
- **Why**: Provides both word-level details and summary statistics

---

### Lines 165-203: Main Block

```python
if __name__ == "__main__":
```
- **Purpose**: Code runs only when script executed directly
- **Why**: Allows import without running test

```python
    # Example usage
    content_results = [
        {"word": "bicycle", "status": "correct", "start": 0.42, "end": 0.91},
        {"word": "racing", "status": "correct", "start": 0.92, "end": 1.41},
        {"word": "is", "status": "missed", "start": None, "end": None},
        {"word": "the", "status": "correct", "start": 1.42, "end": 1.71},
    ]
```
- **Purpose**: Example content alignment results
- **Why**: Demonstrates input format

```python
    pronunciation_results = [
        {
            "word": "bicycle",
            "status": "mispronounced",
            "start": 0.40,
            "end": 0.90,
            "confidence": 0.43,
        },
        {
            "word": "racing",
            "status": "correct",
            "start": 0.91,
            "end": 1.40,
            "confidence": 0.85,
        },
        {
            "word": "the",
            "status": "correct",
            "start": 1.41,
            "end": 1.70,
            "confidence": 0.90,
        },
    ]
```
- **Purpose**: Example pronunciation assessment results
- **Why**: Demonstrates input format

```python
    report = generate_final_report(content_results, pronunciation_results)
    print("Final Report:")
    print(report["summary"])
    print("\nWords:")
    for w in report["words"]:
        print(w)
```
- **Purpose**: Generate and print report
- **Why**: Tests function and shows output format

---

## Summary

This module implements the **unified report generation**:
1. **Merges** content alignment with pronunciation assessment
2. **Applies** decision rules (content errors take precedence)
3. **Combines** timestamps from ASR and pronunciation sources
4. **Calculates** statistics (accuracy, counts, average confidence)
5. **Returns** complete word-level report with summary

The key insight: **Content errors (missed/repeated/substituted) override pronunciation assessment - a word must be correctly spoken before pronunciation can be assessed.**
