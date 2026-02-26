# Listening Feature Reliability and Validation Report

Date: February 23, 2026

## 1) Executive verdict

Current status for the newly implemented Listening features:

- Reliable for **internal prototype and user beta practice**: **Yes (with constraints)**
- Reliable for **commercial high-stakes score claims**: **No (not yet)**

Reason in one line:

- The implementation follows official scoring structures and is stable in-app, but it does not yet include enough calibrated real-response validation and human-rating agreement to claim exam-grade reliability.

## 2) Scope covered in this document

This report evaluates reliability for five Listening tasks now implemented:

1. `Summarize Spoken Text (SST)`
2. `Multiple Choice, Multiple Answers (MCM)`
3. `Multiple Choice, Single Answer (MCS)`
4. `Fill in the Blanks (Type In)`
5. `Select Missing Word (SMW)`

It covers:

- Official scoring alignment.
- Code and route reliability.
- Test evidence currently available.
- Known reliability gaps.
- A production-readiness checklist.

## 3) Official scoring baseline used

The implementation was aligned to Pearson public documents (checked on February 23, 2026):

1. Listening format page:
- https://www.pearsonpte.com/pte-academic/test-format/listening

2. PTE Academic scoring page:
- https://www.pearsonpte.com/pte-academic/scoring

3. PTE Academic Test Taker Score Guide (PDF):
- https://pearsonpte.com/ctf-assets/yqwtwibiobs4/3TQDBW61bfUHn8XJJAXm8v/ef900ec4e82f2043248e485bd4e3b15d/PTE_Academic_Test_Taker_Score_Guide.pdf

## 4) What is implemented (system facts)

### 4.1 Listening evaluator and scoring engine

File: `api/listening_evaluator.py`

Implemented scorers:

1. `evaluate_summarize_spoken_text(...)`
- Trait-based scoring with:
  - `Content` (0-4)
  - `Form` (0-2)
  - `Grammar` (0-2)
  - `Vocabulary` (0-2)
  - `Spelling` (0-2)
- Includes form gate behavior and off-topic gate behavior.
- Returns trait scores + analysis + feedback.

2. `evaluate_multiple_choice_multiple(...)`
- Exact partial-credit logic:
  - `+1` per correct selected option
  - `-1` per incorrect selected option
  - floor at `0`

3. `evaluate_multiple_choice_single(...)`
- Exact correct/incorrect logic:
  - `1` for correct
  - `0` for incorrect or unanswered

4. `evaluate_fill_in_the_blanks(...)`
- Exact per-blank scoring logic:
  - `+1` only for correctly spelled expected word
  - total floor at `0`

5. `evaluate_select_missing_word(...)`
- Exact correct/incorrect logic:
  - `1` for correct
  - `0` for incorrect or unanswered

### 4.2 Backend routes and API contract

File: `api/app.py`

Added pages:

- `/listening/summarize-spoken-text`
- `/listening/multiple-choice-multiple`
- `/listening/multiple-choice-single`
- `/listening/fill-in-the-blanks`
- `/listening/select-missing-word`

Added generic listening APIs:

- `/listening/<task_slug>/get-categories`
- `/listening/<task_slug>/get-catalog`
- `/listening/<task_slug>/get-task`
- `/listening/<task_slug>/audio/<item_id>`
- `/listening/<task_slug>/score`

### 4.3 TTS flexibility and UI controls

Files:

- `api/tts_handler.py`
- `api/static/js/tts_preset_controls.js`
- `api/static/css/style.css`

Implemented:

- Feature-level TTS config for `listening`.
- Shared reusable voice/speed control component.
- Curated 4-voice set with accents:
  - `Blake (US)`, `Amir (IN)`, `Anna (AU)`, `Helen (UK)`
- `Random` voice mode.
- Consistent control styling across listening pages.

### 4.4 Listening data layer

Files:

- `data/reference/listening/summarize_spoken_text/references.json`
- `data/reference/listening/multiple_choice_multiple/references.json`
- `data/reference/listening/multiple_choice_single/references.json`
- `data/reference/listening/fill_in_the_blanks/references.json`
- `data/reference/listening/select_missing_word/references.json`
- `src/shared/paths.py`

Implemented:

- Canonical listening data roots and path resolution.
- Difficulty/category metadata.
- Transcript-based dynamic audio generation for all listening tasks.

## 5) Reliability assessment by feature

### 5.1 Summarize Spoken Text (SST)

Alignment status: **Medium**

What is aligned well:

- Trait-based scoring categories match official structure.
- Form range behavior is implemented.
- Gate behavior exists (form/off-topic). 

Where reliability is weaker:

- Content scoring uses deterministic NLP heuristics (keyword overlap + similarity), not calibrated against large human-scored datasets.
- Pearson mentions additional human content review for this task; current implementation is fully automatic.
- Not yet benchmarked against real candidate responses with expert labels.

Practical reliability verdict:

- Good for guided practice feedback.
- Not sufficient for exam-equivalent score prediction claims.

### 5.2 Multiple Choice, Multiple Answers (MCM)

Alignment status: **High**

What is aligned well:

- Scoring rule implemented exactly as partial credit with penalty per incorrect option.
- Minimum score floor applied.

Where reliability is weaker:

- Item quality depends on authored distractors and transcript quality.
- Small current item bank limits statistical confidence.

Practical reliability verdict:

- Mechanically reliable for scoring.
- Content reliability increases as item bank quality and volume increase.

### 5.3 Multiple Choice, Single Answer (MCS)

Alignment status: **High**

What is aligned well:

- Correct/incorrect scoring is deterministic and directly aligned with official behavior.
- Single-answer constraint is enforced in UI and score endpoint.

Where reliability is weaker:

- Item quality depends on authored distractors and transcript quality.
- Small current item bank limits statistical confidence.

Practical reliability verdict:

- Mechanically reliable for scoring.
- Content reliability increases as item bank quality and volume increase.

### 5.4 Fill in the Blanks (Type In)

Alignment status: **High**

What is aligned well:

- Per-blank scoring with spelling-sensitive correctness.
- Straightforward deterministic scoring with low ambiguity.

Where reliability is weaker:

- Synonym handling is intentionally strict (officially expected word logic), so item authoring must avoid ambiguous gaps.
- Small current dataset size.

Practical reliability verdict:

- Mechanically reliable now.
- Strongly depends on high-quality blank design.

### 5.5 Select Missing Word (SMW)

Alignment status: **High**

What is aligned well:

- Correct/incorrect scoring is deterministic and directly aligned with official behavior.
- Single-answer flow is stable in API and UI.

Where reliability is weaker:

- Item validity depends on strong context and plausible distractors.
- Small current dataset size.

Practical reliability verdict:

- Mechanically reliable for scoring.
- Content reliability depends on item-authoring rigor.

## 6) Test evidence (current)

Executed in project venv:

1. `venv/bin/pytest -q tests/test_listening_evaluator.py`
- Result: `7 passed`

2. `venv/bin/pytest -q tests/test_api_contracts.py`
- Result: `32 passed`

Added tests include:

- Evaluator behavior for SST/MCM/MCS/FIB/SMW.
- Contract tests for new listening routes and score endpoints.
- Partial credit and floor behavior checks.

## 7) Reliability risks still open

### P0 (must address before commercial score claims)

1. No calibration against human-scored gold dataset for SST.
2. No inter-rater agreement benchmark (human vs system).
3. No drift monitoring for scoring stability after content growth.

### P1 (important for scale)

1. Small item bank (currently 5 items per task) may cause overfitting by repeated users.
2. No automated psychometric item analytics (difficulty/discrimination stats).
3. No A/B validation against known public prep datasets.

### P2 (operational)

1. Edge TTS is external and network-dependent for dynamic audio.
2. Need stronger fallback policy when TTS provider is unavailable.

## 8) Production-readiness checklist

Use this checklist to decide if reliability is acceptable for next stage.

### Stage A: Beta-ready (internal + early users)

- [x] Official scoring structure mirrored for target tasks.
- [x] End-to-end APIs stable with tests.
- [x] Deterministic scoring logic for objective tasks.
- [x] Clear score breakdown shown to users.

### Stage B: Commercial pilot-ready

- [ ] Build labeled SST validation set (minimum 500 responses).
- [ ] Measure human-vs-system agreement per trait.
- [ ] Define acceptable error bands by trait.
- [ ] Add score confidence flag and manual-review trigger for low confidence.

### Stage C: Commercial claim-ready

- [ ] Item-level reliability report (difficulty, discrimination, mis-key checks).
- [ ] Ongoing drift dashboard with periodic recalibration.
- [ ] Versioned rubric/scorer releases with changelog.
- [ ] External QA signoff with reproducible benchmark report.

## 9) Recommended reliability metrics to track next

For each release, record:

1. `MCM/MCS/FIB/SMW deterministic consistency`
- same input must always return same score.

2. `SST trait agreement`
- Pearson/Spearman correlation vs expert labels per trait.

3. `Classification agreement`
- exact-band agreement rate and adjacent-band agreement rate.

4. `Calibration quality`
- over/under-prediction by trait and difficulty band.

5. `Operational reliability`
- endpoint success rate, p95 latency, TTS failure rate.

## 10) Final recommendation

Use the current listening implementation for:

- Product demos
- Beta feature launch
- Practice workflow expansion

Do not use it yet for:

- Hard commercial promises that scores are exam-equivalent
- High-stakes admission decision support

Short recommendation:

- Proceed with launch as **practice-mode reliable**.
- Start calibration program immediately to reach **commercial-score reliable**.

---

## Appendix A: Key implementation files

- `api/listening_evaluator.py`
- `api/app.py`
- `api/tts_handler.py`
- `api/static/js/tts_preset_controls.js`
- `api/static/css/style.css`
- `api/templates/summarize_spoken_text.html`
- `api/templates/listening_multiple_choice_multiple.html`
- `api/templates/listening_multiple_choice_single.html`
- `api/templates/listening_fill_in_the_blanks.html`
- `api/templates/listening_select_missing_word.html`
- `data/reference/listening/summarize_spoken_text/references.json`
- `data/reference/listening/multiple_choice_multiple/references.json`
- `data/reference/listening/multiple_choice_single/references.json`
- `data/reference/listening/fill_in_the_blanks/references.json`
- `data/reference/listening/select_missing_word/references.json`
- `tests/test_listening_evaluator.py`
- `tests/test_api_contracts.py`
