# Speech Pipeline Baseline

## Scope
Shared backend flow for speaking tasks that capture user audio.

## Pipeline
1. UI records audio (`MediaRecorder`) in page template.
2. API converts input to 16kHz mono wav via `ffmpeg` (`convert_to_wav` in `api/app.py`).
3. ASR transcription via `pte_core.asr.voice2text`.
4. MFA alignment via Docker path in `api/validator.py` (or ASR-only fallback if unavailable).
5. Word-level analysis:
- lexical diff (`compare_text`),
- phoneme/stress checks,
- pause analysis.
6. Response JSON returned by `/check_stream` (or background job status endpoints).

## Shared Outputs
- transcript
- words[] with status/timing/phoneme fields
- pauses[]
- summary: total/correct/pause_penalty
- meta/cache fields

## Remaining Improvements
- Add unified 0-90 scaled score service for speaking tasks.
- Improve fallback behavior transparency when MFA is unavailable.
- Add latency budget monitoring per accent/model.
