# Detailed Architecture Docs

This folder is for implementation-level documentation of the code paths that are currently active in this repository.

Current detailed docs:

- `read_aloud_architecture.md` - live Read Aloud request flow, service topology, scoring pipeline, runtime artifacts, and fallback behavior.

Scope rules for this folder:

- Prefer the runtime path that is actually wired into `api/app.py`.
- Call out legacy or exploratory modules when they exist, but label them clearly as non-primary.
- Use technical terminology from the implementation: ASR, MFA, TextGrid, G2P, phoneme alignment, stress analysis, pause penalties, and NDJSON streaming.
