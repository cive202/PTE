# Describe Image

## Feature (Short)
User describes an image orally; system scores meaning coverage, pronunciation, and fluency-like structure.

## Real PTE (Public)
- Public guidance uses a short prep window plus capped response window (commonly 25s prep + 40s response).
- Public descriptors focus on content, oral fluency, and pronunciation; full scoring model is proprietary.
- Pearson public tips also warn against overusing memorized templates.

## Our Implementation
- Page: `api/templates/describe_image.html`
- Task APIs: `/describe-image/get-image`, `/speaking/describe-image/get-topics`
- Async scoring: `/describe-image/submit`, `/describe-image/status/<job_id>`
- Evaluator: `api/image_evaluator.py`
- Data: `data/reference/describe_image/references.json` + images directory
- Speech analysis enrichment from shared pipeline (`align_and_validate`)
- Runtime timing config is returned by the backend and drives the prep + speaking countdowns in the UI.
- Scoring now includes semantic similarity, keyword coverage, number/data coverage, MFA pronunciation, duration-aware fluency, and a conservative content gate that fires on irrelevant/template-heavy answers.

## Simple Architecture
Image prompt -> backend timing config -> prep countdown -> speaking countdown (auto-stop) -> ASR + MFA -> `evaluate_description()` + `detect_memorized_template()` -> score detail + gated feedback -> user sees sub-scores, transcription overlay, timing hints.

## Reliability
- Strong feature depth for practice (semantic + keyword + number coverage + pronunciation + duration-aware fluency).
- Scoring is still heuristic and should be calibrated against human-scored data for production fairness.

## Remaining Improvements
- Add multi-reference answer banks per image.
- Add robust chart-value extraction checks for data accuracy.
- Replace regex structure checks with discourse-model scoring.
- Calibrate thresholds (content gate + score bands) on a labeled validation set.

## References
- https://www.pearsonpte.com/articles/pte-academic-test-tips-describe-image
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide.pdf
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE-Academic-Concordance-study.pdf
