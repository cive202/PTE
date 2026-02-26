# Repeat Sentence

## Feature (Short)
User listens to a sentence and repeats it from memory.

## Real PTE (Public)
- In PTE Academic Part 1, prompt audio is typically 3-9 seconds, response time 15 seconds.
- Public scoring is machine-based and rewards accurate repetition; exact weighting is not fully public.

## Our Implementation
- Page: `api/templates/repeat_sentence.html`
- Prompt APIs: `/speaking/repeat-sentence/get-topics`, `/speaking/repeat-sentence/get-task`
- Prompt audio source: static files under `data/reference/repeat_sentence/audio/`
- Submission/scoring: `/check_stream` with `feature=repeat_sentence`
- Shared scoring pipeline: same as `docs/new/architecture/speaking/read_aloud.md`

## Simple Architecture
Prompt audio -> user recording -> `/check_stream` -> shared speech pipeline -> word-level status + pause metrics

## Reliability
- Practice-ready for pronunciation and recall pressure.
- Same scoring limitations as Read Aloud baseline (not fully calibrated to Pearson scale).

## Remaining Improvements
- Add sequence-order-specific content scoring for repeat-sentence strictness.
- Add short-sentence memory penalties distinct from read-aloud behavior.
- Increase sentence bank diversity by accent and speaking rate.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
