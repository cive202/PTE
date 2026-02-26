# Writing: Write Email

## Feature (Short)
User writes task-focused email response with tone and structure requirements.

## Real PTE (Public)
- This task is part of PTE Core (not PTE Academic).
- Public PTE Core format: prompt text up to 100 words, answer time 9 minutes.

## Our Implementation
- Page: `api/templates/write_email.html`
- APIs: `/writing/write-email/get-*` and `/writing/write-email/score`
- Scorer: `evaluate_write_email()` in `api/writing_evaluator.py`
- Data: `data/reference/writing/write_email/references.json`
- Scoring includes content, formal requirements, email conventions, grammar, vocabulary, and spelling.

## Simple Architecture
Email prompt fetch -> user response -> structure + relevance + language scoring -> feedback and analysis payload

## Reliability
- Good for practical skill training.
- Not yet validated against official PTE Core rater agreement data.

## Remaining Improvements
- Add recipient-intent and tone-classifier checks.
- Add domain templates (work, service, academic) with separate calibration.
- Add benchmark evaluation against real PTE Core-style responses.

## References
- https://www.pearsonpte.com/pte-core/test-format/speaking-writing
