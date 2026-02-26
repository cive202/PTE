# Writing: Summarize Written Text

## Feature (Short)
User reads a passage and writes one-sentence summary.

## Real PTE (Public)
- Public format: source text up to about 300 words; time to answer 10 minutes.
- Public scoring is trait-based (content/form/language quality).

## Our Implementation
- Page: `api/templates/summarize_written_text.html`
- APIs: `/writing/summarize-written-text/get-*` and `/writing/summarize-written-text/score`
- Scorer: `evaluate_summarize_written_text()` in `api/writing_evaluator.py`
- Data: `data/reference/writing/summarize_written_text/references.json`

## Simple Architecture
Prompt fetch -> user one-sentence response -> rubric-like heuristic scoring -> feedback + analysis

## Reliability
- Good for practice feedback loops.
- Needs calibration against expert-rated outputs for exam-grade confidence.

## Remaining Improvements
- Improve content relevance model beyond keyword overlap.
- Add stricter one-sentence parser for edge punctuation cases.
- Add scorer regression suite with gold responses.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf
