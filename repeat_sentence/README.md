# Repeat Sentence Module

PTE-style assessment for **Repeat Sentence** task.

## Overview

**Repeat Sentence** flow:
1. System displays/plays a sentence (audio + text)
2. User repeats the sentence
3. System assesses: **content accuracy** + **pronunciation quality**

## Architecture

This module **reuses all the same components** as `read_aloud`:

- ✅ **Content alignment**: `read_aloud/scorer/word_level_matcher.py`
- ✅ **Pronunciation assessment**: `read_aloud/mfa/` or `read_aloud/wavlm_pronunciation.py`
- ✅ **PTE scoring**: `read_aloud/pte_pronunciation.py` (DP alignment, consistency bonus, etc.)
- ✅ **CMUdict**: `read_aloud/phonetics/cmudict.py`
- ✅ **Accent tolerance**: `read_aloud/phonetics/accent_tolerance.py`

**Key difference**: Optimized for **single sentences** (shorter, simpler than full Read Aloud passages).

## Usage

```python
from repeat_sentence import assess_repeat_sentence_simple

wav_path = "user_repetition.wav"
reference_text = "Higher education prepares students for professional challenges."

result = assess_repeat_sentence_simple(wav_path, reference_text)

# Access results
print(result["summary"])
print(result["summary"].get("pte_pronunciation"))  # PTE scores + feedback
```

## Output Format

Same as `read_aloud`:

```json
{
  "words": [
    {"word": "higher", "status": "correct", "confidence": 0.85, ...},
    ...
  ],
  "summary": {
    "total_words": 8,
    "correct": 7,
    "mispronounced": 1,
    "accuracy": 87.5,
    "pte_pronunciation": {
      "score_pte": 78.5,
      "pte_band": 73,
      "phone": 0.85,
      "stress": 0.80,
      "rhythm": 0.90,
      "consistency_bonus": 0.06,
      "feedback": [
        "Your pronunciation is generally clear and easy to follow.",
        "Try to maintain stress on important words for higher scores."
      ]
    }
  },
  "audio_clear": true,
  "pronunciation_method": "mfa"
}
```

## MFA Usage

**Yes, MFA usage is exactly the same** as Read Aloud:
- Same `assess_pronunciation_mfa()` function
- Same accent-tolerant scoring
- Same PTE-style pronunciation formula
- Same consistency bonus logic

The only difference is **shorter input** (one sentence vs. full passage).

## Integration

To use in your system:

1. **Display sentence** on screen (text + optional audio playback)
2. **Record user's repetition** → save as `.wav`
3. **Call `assess_repeat_sentence_simple(wav_path, reference_text)`**
4. **Display results**: PTE score, band, feedback
