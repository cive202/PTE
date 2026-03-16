# MFA Pause and Word-Gap UI Plan

Date: 2026-03-16

## Bottom line

The speaking pipeline should surface pause timing in the same way it surfaces word pronunciation:

1. punctuation pauses should be visible in the word stream
2. each punctuation mark should expose the ideal pause range and the measured pause
3. overly long non-punctuation gaps should appear as a separate blue gap marker
4. all speaking tasks should use the same UI treatment

This is now the right direction because the backend already evaluates punctuation pauses from MFA timings when MFA is available.

## Important research note

Pearson PTE public docs do **not** publish exact millisecond targets for comma or full-stop pauses.

So any concrete timing range in product code must be treated as an **implementation heuristic**, not an official Pearson rule.

What Pearson does make clear is:

- pronunciation and oral fluency both matter
- long pauses reduce performance
- unnatural breaks hurt delivery

What speech research makes clear is:

- sentence-final pauses are reliably longer than comma-level pauses
- comma-like phrase pauses are shorter and lighter
- fluent within-phrase word gaps are much shorter than punctuation pauses

## Practical ranges adopted

These are product ranges, inferred from:

- existing PTE pause logic already in this repo
- public PTE score-guide wording about long pauses
- read-speech literature showing sentence-final pauses are roughly about 2x comma-like pauses

### Punctuation pause targets

- `,` comma: `0.25s - 0.50s`
- `;` semicolon: `0.35s - 0.65s`
- `:` colon: `0.35s - 0.65s`
- `.` full stop: `0.60s - 1.00s`
- `!` exclamation mark: `0.60s - 1.00s`
- `?` question mark: `0.60s - 1.00s`

### Word-to-word gap target

- normal fluent non-punctuation gap: `0.08s - 0.25s`

If a non-punctuation gap goes above the max bound, the UI should insert a synthetic blue gap marker between the two words.

## UI behavior to keep consistent

For all speaking core pages:

- green punctuation chip: pause inside ideal range
- yellow punctuation chip: pause exists but is too short or too long
- red punctuation chip: pause missing
- blue gap chip: non-punctuation gap exceeds ideal max range

On tap or click:

- punctuation chip should show ideal range, actual gap, boundary words, and timing source
- blue gap chip should show ideal gap range, actual gap, and the two surrounding words

## Current implementation direction

The right implementation path is:

1. keep MFA pause timings as primary when available
2. keep ASR timing only as fallback
3. enrich punctuation rows with pause metadata directly in `api/validator.py`
4. build extra blue gap markers in shared frontend logic from word timings
5. reuse one shared helper for Read Aloud, Repeat Sentence, Describe Image, and Retell Lecture

## Sources

Official:

- Pearson PTE Academic Score Guide: `https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf`

Supporting research and prosody evidence:

- Punctuation effects in reading aloud: `https://www.sciencedirect.com/science/article/pii/0749596X9590002X`
- The role of prosody and punctuation in reading aloud: `https://pmc.ncbi.nlm.nih.gov/articles/PMC2805240/`
- Pause boundaries and punctuation in reading: `https://www.sciencedirect.com/science/article/pii/S0095447097900470`

## Interpretation rule

If someone later asks whether `0.60s - 1.00s` for a full stop is an official Pearson pause rule, the correct answer is:

No. It is a product heuristic derived from speech-timing literature plus the existing PTE-style fluency model in this codebase.
