# Listening: Select Missing Word

## Feature (Short)
User listens and chooses the missing word/phrase at the end of recording.

## Real PTE (Public)
- Objective single-choice task; typically scored as correct/incorrect.
- Public prompt range often around 20-70 seconds.

## Our Implementation
- Page: `api/templates/listening_select_missing_word.html`
- Shared listening APIs under `/listening/select-missing-word/*`
- Scorer: `evaluate_select_missing_word()` in `api/listening_evaluator.py`
- Data: `data/reference/listening/select_missing_word/references.json`
- Same single-choice scoring pattern as `docs/new/architecture/listening/multiple_choice_single.md`.

## Simple Architecture
Task fetch -> audio + options -> single answer submit -> deterministic 1/0 scoring

## Reliability
- High scoring consistency.
- Requires high-quality options to avoid semantic overlap.

## Remaining Improvements
- Add end-of-audio context emphasis hints for feedback.
- Add distractor difficulty tuning by lexical similarity.
- Expand category-balanced question bank.

## References
- https://www.pearsonpte.com/pte-academic/test-format/listening
