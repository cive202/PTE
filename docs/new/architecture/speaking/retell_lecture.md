# Retell Lecture

## Feature (Short)
User listens to a lecture, gets a short preparation window, then retells the main ideas in spoken form.

## Real PTE (Public)
- Public format guidance: lecture prompt is typically around 60-90 seconds, with 10 seconds preparation and 40 seconds response.
- Practical target for learner responses: aim to use most of the 40-second response window (commonly ~25-40 seconds of speech).
- Public scoring guidance: speaking responses are machine-scored with focus on content relevance and speaking quality traits (including oral fluency and pronunciation).
- Public tips also warn against template-style memorized delivery that is weakly related to prompt meaning.

## Our Implementation
- Page: `api/templates/retell_lecture.html`
- APIs: `/retell-lecture/get-categories`, `/retell-lecture/get-catalog`, `/retell-lecture/get-lecture`, `/retell-lecture/audio/<lecture_id>`
- Async scoring: `/retell-lecture/submit`, `/retell-lecture/status/<job_id>`
- Evaluator: `api/lecture_evaluator.py`
- Prompt audio: dynamic Edge TTS via shared voice/speed preset controls (`api/static/js/tts_preset_controls.js`)
- Data: `data/reference/retell_lecture/references.json`
- Runtime timing config is returned by backend (`get_retell_lecture_runtime_config`) and drives UI countdowns.
- UI behavior now mirrors task flow: lecture playback -> auto prep countdown -> auto recording start on timeout (or manual early start) -> auto stop at response limit.
- Evaluation uses semantic similarity + keyword + key-point coverage + MFA-based pronunciation + duration/pace/structure fluency scoring, with conservative content gating.

## Simple Architecture
Lecture metadata -> dynamic TTS prompt -> user recording with timed phases -> ASR + MFA alignment -> `evaluate_lecture()` -> weighted scoring + feedback + transcript overlays.

## Reliability
- Strong for practice usage: runtime-controlled timing, dynamic TTS, pronunciation evidence from MFA, and gated anti-template scoring.
- Still heuristic: final calibration should be validated against human-scored benchmark sets for fairness and stability.

## Remaining Improvements
- Calibrate thresholds and weights on labeled response data.
- Add multi-reference concept maps per lecture to improve coverage robustness.
- Add response-level discourse coherence modeling beyond regex structure cues.

## References
- https://www.pearsonpte.com/articles/pte-academic-test-tips-retell-lecture
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide.pdf
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE-Academic-Concordance-study.pdf
