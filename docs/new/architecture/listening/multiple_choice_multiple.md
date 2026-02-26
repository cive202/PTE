# Listening: Multiple Choice (Multiple Answers)

## Feature (Short)
User listens and selects all correct options.

## Real PTE (Public)
- Public scoring behavior: +1 for each correct selected, -1 for each incorrect selected, minimum 0.

## Our Implementation
- Page: `api/templates/listening_multiple_choice_multiple.html`
- Shared listening APIs under `/listening/multiple-choice-multiple/*`
- Scorer: `evaluate_multiple_choice_multiple()` in `api/listening_evaluator.py`
- Data: `data/reference/listening/multiple_choice_multiple/references.json`
- Uses shared TTS controls (`docs/new/architecture/shared/tts_audio_baseline.md`).

## Simple Architecture
Task fetch -> dynamic audio -> multi-select submit -> deterministic scoring rule -> analysis/feedback

## Reliability
- High mechanical reliability (deterministic rule).
- Final quality still depends on item writing quality.

## Remaining Improvements
- Add distractor analytics and item difficulty stats.
- Add larger item bank with topic balancing.
- Add review mode showing evidence spans from transcript.

## References
- https://www.pearsonpte.com/pte-academic/test-format/listening
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf
