# Reading: Multiple Choice (Single Answer)

## Feature (Short)
User reads passage and selects one best answer.

## Real PTE (Public)
- Objective single-choice task scored as 1/0.

## Our Implementation
- Page: `api/templates/reading_multiple_choice_single.html`
- APIs under `/reading/multiple-choice-single/*`
- Scorer: `evaluate_multiple_choice_single()` in `api/reading_evaluator.py`
- Data: `data/reference/readingset/multiple_choice_multiple/references_single.json`
- Shared objective flow with `docs/new/architecture/reading/multiple_choice_multiple.md`.

## Simple Architecture
Passage fetch -> single option submit -> deterministic 1/0 scoring

## Reliability
- Very stable scoring behavior.
- Depends on unambiguous question design.

## Remaining Improvements
- Add explainable wrong-answer feedback.
- Add item discrimination metrics.
- Add larger corpus per CEFR-like band.

## References
- https://www.pearsonpte.com/pte-academic/test-format/reading
