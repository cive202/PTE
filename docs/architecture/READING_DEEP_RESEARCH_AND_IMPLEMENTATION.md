# Reading Deep Research and Implementation

Date: February 23, 2026

## 1) Scope

This document covers three Reading task types requested for this system:

1. `Fill in the Blanks (Dropdown)` (Reading and Writing)
2. `Multiple Choice, Multiple Answers` (Reading)
3. `Multiple Choice, Single Answer` (Reading)

It explains:

- How Pearson describes these tasks in public documentation.
- How they are scored in real PTE.
- How to implement them in this codebase with architecture consistency.

## 2) Official Sources Used

Primary references (checked on February 23, 2026):

1. Pearson PTE Academic Test Taker Score Guide (2025 update)
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf

2. Pearson PTE Academic Test Tips Booklet
- https://www.pearsonpte.com/pteservice/newarticlecontent/content/resources/PTE_Academic_Test_Tips_Booklet.pdf

3. Pearson Concordance Report (item-type technical summary)
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/research/Ref-65-Concordance-Report-PTE-Academic-Can-Do-Statements-and-English-Language-Test-Scores.pdf

## 3) Real PTE Behavior (What Matters for Implementation)

## 3.1 Reading section context

- The score guide lists Reading as Part 2 and indicates an overall section time window.
- Item counts are variable by form, so backend should support item banks and randomization.

## 3.2 Multiple Choice, Multiple Answers (Reading)

From Pearson docs:

- User reads a passage and can choose more than one answer.
- Concordance technical summary describes this item as passage-based (`~300 words`) with multiple options and multiple correct responses.
- Scoring is partial-credit with negative marking:
  - `+1` each correct selected option
  - `-1` each incorrect selected option
  - minimum score `0`

Implementation implication:

- This is deterministic and objective.
- Correct/incorrect key quality is the main reliability driver.

## 3.3 Multiple Choice, Single Answer (Reading)

From Pearson docs:

- User reads a passage and selects exactly one option.
- Concordance technical summary lists this as a short passage item (`~70-110 words`) with one best answer among options.
- Scoring is binary:
  - `1` for correct
  - `0` for incorrect

Implementation implication:

- Deterministic objective scoring.
- Distractor quality matters more than scoring logic.

## 3.4 Fill in the Blanks (Dropdown) (Reading and Writing)

From Pearson docs:

- A short passage has several blanks.
- Each blank has a dropdown list of options.
- User picks one option per blank.
- Concordance technical summary describes this item as approximately `100-200` words with around `4-5` dropdown blanks.
- Scoring is per blank:
  - `1` point for each correct blank
  - no negative marking

Implementation implication:

- Deterministic objective scoring.
- Good blank design (unambiguous context-fit answer) is essential.

## 4) Architecture Pattern for This Repo

To stay aligned with existing Listening/Writing architecture:

1. Data-backed item banks in `data/reference/...`.
2. Evaluator module with deterministic scoring functions.
3. Generic routes per task group:
   - `get-categories`
   - `get-catalog`
   - `get-task`
   - `score`
4. Frontend templates per task using the same setup/results UI pattern.

This was selected because Listening already uses this structure and it is stable in this project.

## 4.1 Psychometric weighting note (official research publication)

The Concordance report includes item-contribution signals for Reading:

- MCS: `~2.5%`
- MCM: `~5.0%`
- Dropdown FIB: `~27.5%`

Implementation inference:

- Prioritize item quality and validation most heavily for Dropdown FIB because quality drift there has outsized impact on Reading skill estimation.

## 5) Implemented Design (Now Added)

## 5.1 Backend evaluator

File: `api/reading_evaluator.py`

Added:

- `get_reading_difficulties(...)`
- `get_reading_catalog(...)`
- `get_reading_task(...)`
- `evaluate_multiple_choice_multiple(...)`
- `evaluate_multiple_choice_single(...)`
- `evaluate_fill_in_the_blanks_dropdown(...)`

Scoring behavior:

- MCM: exact `+1/-1/min 0`
- MCS: exact `1/0`
- Dropdown FIB: exact `+1 each correct blank`

## 5.2 API routes

File: `api/app.py`

Added reading pages:

- `/reading/multiple-choice-multiple`
- `/reading/multiple-choice-single`
- `/reading/fill-in-the-blanks-dropdown`

Added generic reading APIs:

- `/reading/<task_slug>/get-categories`
- `/reading/<task_slug>/get-catalog`
- `/reading/<task_slug>/get-task`
- `/reading/<task_slug>/score`

## 5.3 Data layer

Files:

- `data/reference/readingset/multiple_choice_multiple/references.json`
- `data/reference/readingset/multiple_choice_multiple/references_single.json`
- `data/reference/readingset/multiple_choice_multiple/references_fib_dropdown.json`
- `src/shared/paths.py`

Notes:

- Added canonical/legacy path constants for Reading datasets.
- Added runtime directory creation hooks in `ensure_runtime_dirs()`.

## 5.4 Frontend pages

Files:

- `api/templates/reading_multiple_choice_multiple.html`
- `api/templates/reading_multiple_choice_single.html`
- `api/templates/reading_fill_in_the_blanks_dropdown.html`
- `api/templates/dashboard.html`

UI behavior:

- Topic catalog and difficulty filter.
- Card-based task selection.
- Immediate deterministic score report with analysis + feedback.

## 5.5 Test coverage

Files:

- `tests/test_reading_evaluator.py`
- `tests/test_api_contracts.py` (reading route + score contracts)

## 6) Real PTE vs Our Practice System

## What now matches well

- Core response type per task.
- Core scoring formulas for all three tasks.
- Multi-item bank delivery with category filtering.

## What remains intentionally different

- This is practice-mode, not secured exam-delivery mode.
- No section timer lock, navigation lock, or proctoring constraints.
- No psychometric calibration or item-response-theory analytics yet.

## 7) Next Reliability Steps

1. Expand item bank volume and validate distractor quality.
2. Add item-level analytics:
   - option selection frequency
   - distractor discrimination
   - miss-rate by difficulty band
3. Add timed simulation mode for full Reading section behavior.
4. Add QA checks for ambiguous blanks in dropdown FIB.

## 8) Summary

Reading features are now implemented using the same production pattern already used by Listening/Writing in this repo, with official PTE scoring logic mirrored for:

- `MCM (+1/-1/min0)`
- `MCS (1/0)`
- `FIB Dropdown (+1 per blank)`
