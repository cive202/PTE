# Listening: Multiple Choice (Single Answer)

## Feature (Short)
User listens and chooses one best answer.

## Real PTE (Public)
- Public rule is objective: correct answer scores 1, otherwise 0.

## Our Implementation
- Page: `api/templates/listening_multiple_choice_single.html`
- Shared listening route family under `/listening/multiple-choice-single/*`
- Scorer: `evaluate_multiple_choice_single()` in `api/listening_evaluator.py`
- Data: `data/reference/listening/multiple_choice_single/references.json`
- Shared architecture with MCM task in `docs/new/architecture/listening/multiple_choice_multiple.md`.

## Simple Architecture
Task fetch -> audio play -> single option submit -> deterministic 1/0 scoring

## Reliability
- Very high scoring consistency.
- Item validity depends on passage and distractor design.

## Remaining Improvements
- Add rationale feedback by wrong-option type.
- Add psychometric checks for option ambiguity.
- Expand balanced item inventory.

## References
- https://www.pearsonpte.com/pte-academic/test-format/listening
