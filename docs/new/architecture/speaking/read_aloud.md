# Read Aloud

## Feature (Short)
User reads on-screen text aloud; system evaluates spoken delivery against the displayed passage.

## Real PTE (Public)
- In PTE Academic Part 1, prompt text is up to 60 words.
- Public guidance indicates machine scoring for speaking traits; exact model internals are not published.

## Our Implementation
- Page: `api/templates/index.html`
- Prompt APIs: `/speaking/read-aloud/get-topics`, `/speaking/read-aloud/get-passage`
- Submission/scoring: `/check_stream` with `feature=read_aloud`
- Engine: `api/validator.py` (`align_and_validate_gen`)
- Data: `data/reference/read_aloud/references.json`

## Simple Architecture
UI text selection -> record audio -> `/check_stream` -> ASR + MFA + pause analysis -> word-level result JSON

## Reliability
- Good for granular pronunciation/fluency feedback.
- Current UI score is accuracy-style summary (`correct/total`), not a calibrated exam-equivalent 0-90 scale.

## Remaining Improvements
- Add stable scaled scoring layer (content/pronunciation/fluency -> 0-90).
- Add benchmark set with expert-rated samples.
- Add stricter handling of reading hesitations and self-corrections.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf
