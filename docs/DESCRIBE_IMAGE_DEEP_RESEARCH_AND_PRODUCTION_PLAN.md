# Describe Image Deep Research and Production Plan

Date: February 26, 2026

## 1) Executive summary

This implementation aligns the local `Describe Image` practice flow more closely to public PTE guidance:

- Adds explicit **prep + speaking timing** in the UX.
- Adds a **content gate** so irrelevant/template-heavy responses can be scored as zero overall (matching published scoring behavior notes).
- Adds **duration-aware fluency signals** (not just text length).
- Keeps the existing pronunciation and semantic pipeline, but with stronger safeguards and clearer diagnostics.

## 2) Official PTE behavior (public sources)

From Pearson public materials:

- Describe Image is a speaking item scored on **Content, Oral Fluency, Pronunciation**.
- The task uses a short preparation period and a limited speaking window (public references commonly list **25s prep + 40s response**).
- Pearson warns that **memorized templates** can reduce content validity.
- Pearson guidance states that if content is effectively zero for this item, fluency/pronunciation do not contribute to score.

## 3) Previous implementation gaps

- No enforced prep countdown and no hard speaking window on frontend.
- Fluency relied on structure + length only (no speaking-time signal).
- No explicit content gate for irrelevant/template-heavy responses.
- Backend/frontend contract did not carry timing metadata.

## 4) Production implementation delivered

### Backend

Files:
- `api/image_evaluator.py`
- `api/app.py`

Changes:
- Added runtime task config via `get_describe_image_runtime_config()`:
  - `prep_seconds`
  - `response_seconds`
  - `recommended_response_min_seconds`
  - `recommended_response_max_seconds`
- Added conservative content gating logic:
  - too short,
  - weak relevance,
  - template-heavy + low relevance.
- Added template-risk detection and number/data coverage metrics.
- Added duration-aware fluency scoring:
  - structure fit,
  - length ratio,
  - speaking duration fit.
- Extended evaluation input to accept optional `speech_duration_seconds`.
- API now returns timing config in:
  - `/describe-image/get-image`
  - `/speaking/describe-image/get-topics`
- `/describe-image/submit` now accepts optional `recording_seconds` and stores it in the job context.

### Frontend

File:
- `api/templates/describe_image.html`

Changes:
- Added visible timing panel.
- Start flow now begins preparation countdown first, then recording starts automatically.
- Speaking countdown is shown while recording.
- Auto-stop at configured speaking limit.
- Captures measured recording duration and sends it to backend with submission.
- Resets timing/session state correctly on topic switch/new image/re-record.

## 5) Reliability and safety notes

- Content gating is intentionally conservative to avoid false-zero on valid answers.
- Template detection alone does not zero a response; it must coincide with weak relevance signals.
- If duration cannot be inferred from MFA, frontend-measured duration is used as fallback.
- Timing values are environment-configurable for operational tuning.

## 6) Remaining roadmap (next production steps)

1. Add multi-reference answer banks per image and average content scoring.
2. Add chart-data extraction checks (numeric consistency vs prompt values).
3. Add evaluator unit tests for gate thresholds and timing sensitivity.
4. Calibrate score bands against a human-scored validation set.

## 7) Sources (public)

- Pearson PTE test tips: Describe Image  
  https://www.pearsonpte.com/articles/pte-academic-test-tips-describe-image
- Pearson PTE Academic test taker score guide (public PDF)  
  https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide.pdf
- Pearson PTE concordance and test overview PDF (timing overview reference)  
  https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE-Academic-Concordance-study.pdf

