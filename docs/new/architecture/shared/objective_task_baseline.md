# Objective Task Baseline

## Scope
Shared design for objective tasks (MCQ/FIB) in listening and reading.

## Common Flow
1. UI fetches catalog/categories/task.
2. User selects options or fills blanks.
3. UI submits to `/listening/<task>/score` or `/reading/<task>/score`.
4. Evaluator applies deterministic rule.
5. API returns score + analysis + feedback.

## Shared Rule Types
- Single-choice: 1/0.
- Multiple-choice multiple answers: +1 correct, -1 incorrect, floor at 0.
- Fill in blanks: +1 per correct blank.

## Code Locations
- Route logic: `api/app.py`
- Listening objective evaluators: `api/listening_evaluator.py`
- Reading objective evaluators: `api/reading_evaluator.py`

## Remaining Improvements
- Add item-statistics telemetry (difficulty, discrimination, distractor quality).
- Add anti-guessing analytics and adaptive practice modes.
- Add authoring QA checks for ambiguous options.
