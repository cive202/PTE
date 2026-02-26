# System Baseline

## What This System Is
A Flask-based PTE practice platform with:
- speaking tasks (audio recording + ASR/MFA analysis),
- listening/reading/writing tasks (deterministic or rubric-like scoring),
- dynamic TTS playback for listening-style prompts.

## Runtime Components
- API and routes: `api/app.py`
- Speaking analysis engine: `api/validator.py`
- Task evaluators:
  - `api/image_evaluator.py`
  - `api/lecture_evaluator.py`
  - `api/listening_evaluator.py`
  - `api/reading_evaluator.py`
  - `api/writing_evaluator.py`
- TTS abstraction: `api/tts_handler.py`
- TTS preset UI controller: `api/static/js/tts_preset_controls.js`
- Data path resolution: `src/shared/paths.py`

## Simple Architecture
Browser UI -> Flask route -> evaluator/service -> JSON score -> persisted attempt artifact

## Reliability Position
- Strong for objective scoring rules (MCQ/FIB style).
- Medium for heuristic language scoring tasks.
- Not equivalent to Pearson production black-box scoring.

## Remaining Improvements
- Add calibrated evaluation datasets with human rater agreement.
- Add versioned score-calibration config per task.
- Add periodic regression benchmarks per release.
