# Reading: Fill in the Blanks (Dropdown)

## Feature (Short)
User fills passage blanks by selecting words from dropdown options.

## Real PTE (Public)
- Publicly described as objective blank completion in Reading.
- Scoring is typically 1 point per correct blank.

## Our Implementation
- Page: `api/templates/reading_fill_in_the_blanks_dropdown.html`
- APIs under `/reading/fill-in-the-blanks-dropdown/*`
- Scorer: `evaluate_fill_in_the_blanks_dropdown()` in `api/reading_evaluator.py`
- Data: `data/reference/readingset/multiple_choice_multiple/references_fib_dropdown.json`

## Simple Architecture
Template fetch with blanks/options -> user dropdown selections -> per-blank exact scoring

## Reliability
- High deterministic reliability.
- Depends on blank-option quality and context clarity.

## Remaining Improvements
- Add automatic ambiguity checks in content pipeline.
- Add analytics for frequently missed blanks.
- Add distractor tuning based on part-of-speech confusion.

## References
- https://www.pearsonpte.com/pte-academic/test-format/reading
