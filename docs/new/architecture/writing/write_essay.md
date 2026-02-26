# Writing: Write Essay

## Feature (Short)
User writes extended argumentative essay on given prompt.

## Real PTE (Public)
- Public format: prompt about 2-3 sentences, answer time 20 minutes.
- Public rubric is multi-trait (content/form/structure/coherence/language control).

## Our Implementation
- Page: `api/templates/write_essay.html`
- APIs: `/writing/write-essay/get-*` and `/writing/write-essay/score`
- Scorer: `evaluate_write_essay()` in `api/writing_evaluator.py`
- Data: `data/reference/writing/write_essay/references.json`
- Shares language helper logic with SWT and Write Email in same evaluator module.

## Simple Architecture
Essay prompt fetch -> user response -> trait scoring (content, form, coherence, grammar, vocabulary, spelling) -> feedback

## Reliability
- Solid for formative coaching.
- Still heuristic compared with production high-stakes scoring systems.

## Remaining Improvements
- Add argument quality model (claim/evidence/counterargument coverage).
- Add calibration against human-rated essay corpus.
- Add prompt-type-aware scoring profiles.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
