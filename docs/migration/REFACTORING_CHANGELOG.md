# Refactoring Changelog

## 2026-02-11 - Phase 0 and Phase 1 (Foundations)

## Completed

1. Added architecture and migration planning docs:
   - `ARCHITECTURE_ANALYSIS.md`
   - `TARGET_ARCHITECTURE.md`
   - `MIGRATION_PLAN.md`
2. Added baseline regression tests:
   - API contract tests
   - mocked validator integration tests
   - startup diagnostics tests
3. Added startup diagnostics module:
   - `api/startup_diagnostics.py`
4. Introduced centralized shared configuration:
   - `src/shared/paths.py`
   - `src/shared/services.py`
5. Rewired runtime modules to shared config (backward-compatible):
   - `api/app.py`
   - `api/file_utils.py`
   - `api/image_evaluator.py`
   - `api/lecture_evaluator.py`
   - `api/validator.py`
   - `pte_core/asr/voice2text.py`
   - `pte_core/asr/phoneme_recognition.py`
   - `api/startup_diagnostics.py`

## Behavior/Compatibility Notes

1. Existing API routes and payload contracts were preserved.
2. Legacy paths (`corpus/`, `data_2/`, `PTE_MFA_TESTER_DOCKER/`) remain valid defaults.
3. Service URLs can now be configured via environment variables without code edits.
4. Full test suite remains required as gate for each subsequent migration phase.

## Next Planned Unit

## 2026-02-11 - Phase 2 (Directory and Data Cleanup)

## Completed

1. Centralized reference data under canonical structure:
   - `data/reference/read_aloud/references.json`
   - `data/reference/repeat_sentence/references.json`
   - `data/reference/repeat_sentence/audio/*`
   - `data/reference/describe_image/references.json`
   - `data/reference/describe_image/images/*`
   - `data/reference/retell_lecture/references.json`
   - `data/reference/retell_lecture/lectures/*`
2. Centralized user upload data:
   - active upload/write path now `data/user_uploads/`
   - legacy `corpus/` data migrated into `data/user_uploads/`
3. Centralized MFA runtime artifacts:
   - new runtime path `data/processed/mfa_runs/`
   - validator now mounts models from `data/models/mfa` and runtime from `data/processed/mfa_runs`
   - legacy run/output artifacts moved to `data/archive/mfa_legacy/`
4. Decluttered project root:
   - moved docs to `docs/operations/`
   - moved scripts to `scripts/windows/` and `scripts/data/`
   - moved service folders to `docker/asr-grammar/` and `docker/phoneme-service/`
   - moved transient/tool metadata into `.cache/garbage/`
5. Added compatibility shim:
   - root `pte_tools.py` now re-exports from `src/shared/pte_tools.py`
6. Added cleanup utility:
   - `scripts/temp-delete.sh` (dry-run by default, `--force` to delete)

## Behavior/Compatibility Notes

1. Existing API routes and response contracts are preserved.
2. Shared path config resolves canonical paths first and supports legacy fallback where needed.
3. Docker compose build contexts updated for moved service directories.

## Next Planned Unit

1. Move remaining runtime packages into `src/` with import-compat wrappers.
2. Relocate compose/config into `docker/` and `config/` with minimal root entrypoints.
