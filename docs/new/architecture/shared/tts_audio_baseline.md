# TTS and Audio Baseline

## Scope
Dynamic prompt audio generation for listening-style experiences and retell lecture.

## Current Provider
- Provider: Edge TTS (`edge_tts` library).
- Backend abstraction: `api/tts_handler.py`.
- API endpoints: `/api/tts`, `/api/tts/options`, `/api/tts/voices`.

## Curated Voice Presets
Used in listening controls (`api/static/js/tts_preset_controls.js`):
- Blake (US)
- Amir (IN)
- Anna (AU)
- Helen (UK)
- plus Random mode

## Controls
- speed: `x0.85`, `x1.0`, `x1.15`
- voice selection + random repick
- provider/speed/voice serialized into audio URL query params

## Remaining Improvements
- Add provider failover (open-source local TTS fallback).
- Add per-item audio caching at CDN/storage layer.
- Add synthetic voice quality checks and loudness normalization.
