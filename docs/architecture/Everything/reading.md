# Reading Architecture

## 1. Overview

The Reading module provides deterministic scoring for objective PTE-style Reading tasks.

- **Input**: Passage item + user selections
- **Output**: Task score + analysis + feedback

Implemented tasks:

1. Multiple Choice, Multiple Answers
2. Multiple Choice, Single Answer
3. Fill in the Blanks (Dropdown)

## 2. Flow

```mermaid
graph TD
    A[Browser Task Page] --> B[/reading/<task>/get-catalog];
    A --> C[/reading/<task>/get-task];
    C --> D[Render Passage + Options];
    D --> E[/reading/<task>/score];
    E --> F[Deterministic Evaluator];
    F --> G[JSON Score + Analysis + Feedback];
```

## 3. Components

- **Routes**: `api/app.py`
- **Scoring engine**: `api/reading_evaluator.py`
- **Reference data**: `data/reference/readingset/multiple_choice_multiple/*.json`
- **Templates**:
  - `api/templates/reading_multiple_choice_multiple.html`
  - `api/templates/reading_multiple_choice_single.html`
  - `api/templates/reading_fill_in_the_blanks_dropdown.html`

## 4. Scoring Rules

1. **MCM**: `+1` correct selected, `-1` incorrect selected, minimum `0`
2. **MCS**: `1` for correct, `0` for incorrect/unanswered
3. **FIB Dropdown**: `1` per correct blank, no negative marking

## 5. Data Contract

Catalog item:

- `id`
- `title`
- `topic`
- `difficulty`

Task payload:

- MCM/MCS: `passage`, `question`, `options[]`
- FIB Dropdown: `passage_template`, `blanks[]` (`id`, `options[]`)

## 6. Reliability Notes

- Scoring is deterministic and objective.
- Reliability depends mainly on item authoring quality (correct key + distractors + unambiguous blanks).
- This module is practice-focused and does not replicate secure exam delivery constraints.
