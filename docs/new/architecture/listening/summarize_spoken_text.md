# Listening: Summarize Spoken Text

## Feature (Short)
User listens to audio and writes a concise summary.

## Real PTE (Public)
- PTE Academic listening format: recording about 60-90 seconds.
- Public rubric categories include content/form/language traits; exact production weights are proprietary.

## Our Implementation
- Page: `api/templates/summarize_spoken_text.html`
- APIs: `/listening/summarize-spoken-text/get-categories`, `/get-catalog`, `/get-task`, `/audio/<id>`, `/score`
- Scorer: `evaluate_summarize_spoken_text()` in `api/listening_evaluator.py`
- Data: `data/reference/listening/summarize_spoken_text/references.json`
- Prompt audio: dynamic TTS via Edge.

## Simple Architecture
Fetch item -> synthesize transcript audio -> user writes summary -> rubric-like heuristic scoring + feedback

## Reliability
- Good for guided practice.
- Not yet calibrated against large human-rated corpora.

## Remaining Improvements
- Add human-labeled calibration set and score agreement checks.
- Add stronger semantic topic coverage model.
- Add anti-copy and paraphrase-quality signals.

## References
- https://www.pearsonpte.com/pte-academic/test-format/listening
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf
