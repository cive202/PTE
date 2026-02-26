# Reading: Multiple Choice (Multiple Answers)

## Feature (Short)
User reads passage and selects all correct responses.

## Real PTE (Public)
- Public rule: +1 for each correct selected, -1 for each incorrect selected, minimum 0.

## Our Implementation
- Page: `api/templates/reading_multiple_choice_multiple.html`
- APIs: `/reading/multiple-choice-multiple/get-categories`, `/get-catalog`, `/get-task`, `/score`
- Scorer: `evaluate_multiple_choice_multiple()` in `api/reading_evaluator.py`
- Data: `data/reference/readingset/multiple_choice_multiple/references.json`

## Simple Architecture
Passage fetch -> option selection -> deterministic partial-credit scoring

## Reliability
- High deterministic consistency.
- Reliability depends on item authoring quality.

## Remaining Improvements
- Add distractor quality analytics.
- Expand topic and difficulty coverage.
- Add passage readability checks during authoring.

## References
- https://www.pearsonpte.com/pte-academic/test-format/reading
