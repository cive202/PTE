# Listening: Fill in the Blanks (Type In)

## Feature (Short)
User types missing words in a transcript while/after listening.

## Real PTE (Public)
- Objective scoring: 1 point per correctly spelled blank.
- Public format: recording duration commonly 30-60 seconds.

## Our Implementation
- Page: `api/templates/listening_fill_in_the_blanks.html`
- Shared listening APIs under `/listening/fill-in-the-blanks/*`
- Scorer: `evaluate_fill_in_the_blanks()` in `api/listening_evaluator.py`
- Data: `data/reference/listening/fill_in_the_blanks/references.json`

## Simple Architecture
Task fetch (template + blank ids) -> audio playback -> typed responses -> exact-match blank scoring

## Reliability
- High deterministic reliability when blank keys are unambiguous.
- Sensitive to spelling and canonical answer definitions.

## Remaining Improvements
- Add optional accepted-variant list per blank where justified.
- Add typo-tolerance mode for learning-only analytics (not scoring).
- Add blank design QA checks to avoid multiple valid answers.

## References
- https://www.pearsonpte.com/pte-academic/test-format/listening
