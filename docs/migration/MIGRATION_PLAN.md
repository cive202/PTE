# Migration Plan: Safe Incremental Refactor

## 1) Non-Negotiable Constraints

1. No API contract breakage for existing frontend routes.
2. No destructive data move before validated copy.
3. Full tests after every logical migration unit.
4. Keep backward-compatible imports until final cleanup.
5. Keep rollback trivial (small diffs per step).

---

## 2) Backward Compatibility Strategy

## 2.1 Import compatibility layer (preferred over symlinks)

Use wrapper modules during migration:

1. Keep legacy package paths (`api`, `pte_core`, `read_aloud`, `repeat_sentence`).
2. Move real implementation to `src/...`.
3. In legacy modules, re-export from `src` and raise deprecation warnings.

Example pattern:

```python
# api/validator.py (compat wrapper, temporary)
from src.api.validator import *  # noqa: F401,F403
```

Why wrappers over symlinks:

1. Better cross-platform behavior.
2. Cleaner deprecation messaging.
3. Easier to audit and remove in final cutover.

## 2.2 Path compatibility layer

1. Introduce `src/shared/paths.py` first.
2. Keep legacy roots (`corpus/`, `data_2/`, `PTE_MFA_TESTER_DOCKER/`) readable.
3. Write new outputs to canonical `data/...` paths.
4. During transition, support dual-read where needed (new path first, fallback old path).

## 2.3 Service URL compatibility

1. Move hardcoded localhost URLs into config/env.
2. Keep default values matching current behavior (`localhost:8000`, `localhost:8001`).

---

## 3) Testing Strategy and Quality Gates

## 3.1 Baseline status

Current baseline (already added and passing):

1. API contract tests for key routes and NDJSON stream.
2. Mocked integration tests for MFA fallback/TextGrid paths.
3. Startup diagnostics tests.

## 3.2 Required test sets per migration step

For each step run:

1. `./venv/bin/python -m pytest tests/test_api_contracts.py`
2. `./venv/bin/python -m pytest tests/test_validator_integration.py`
3. `./venv/bin/python -m pytest tests/test_startup_diagnostics.py`
4. `./venv/bin/python -m pytest` (full local suite)

## 3.3 Runtime smoke checks (manual or scripted)

1. `GET /` returns 200.
2. `GET /speaking/read-aloud/get-topics` schema unchanged.
3. `GET /speaking/repeat-sentence/get-task` schema unchanged.
4. `POST /api/grammar` proxy behavior unchanged.
5. `POST /check_stream` emits NDJSON progress then result.
6. Docker health endpoints:
   - `http://localhost:8000/health`
   - `http://localhost:8001/health`

---

## 4) Migration Order (Incremental)

## Phase 0 (done): Safety Net

1. Add test harness and contract/integration coverage.
2. Add startup diagnostics utility.
3. Validate green baseline.

## Phase 1: Introduce Config and Canonical Paths (no moves yet)

1. Add centralized config module (`src/shared/config.py`, `src/shared/paths.py`).
2. Replace hardcoded path/URL constants in runtime code with config lookups.
3. Keep current physical directories unchanged.
4. Gate: full tests + smoke checks pass.

## Phase 2: Data Layout Migration (copy-first)

1. Create `data/reference`, `data/user_uploads`, `data/processed`, `data/models`, `data/archive`.
2. Copy static `data_2/*` into `data/reference/*`.
3. Route new uploads to `data/user_uploads` while still reading old `corpus/` where needed.
4. Route new MFA run/output artifacts to `data/processed/mfa_runs`.
5. Move legacy MFA artifacts into `data/archive` after verification.
6. Gate: contract tests + one end-to-end read-aloud run works.

## Phase 3: Code Reorganization with wrappers

1. Create `src/api`, `src/core`, `src/modules`, `src/services`, `src/shared`.
2. Move one logical area at a time:
   - first `api/file_utils.py` and pure helpers,
   - then evaluators (`image_evaluator`, `lecture_evaluator`),
   - then validator internals,
   - finally route layer.
3. Leave temporary wrappers at old import paths.
4. Gate after each moved unit: full tests green.

## Phase 4: Docker Layout Cleanup

1. Move Docker contexts into `docker/asr-grammar`, `docker/phoneme-service`.
2. Move compose file into `docker/compose/docker-compose.yml`.
3. Add root-level launcher script or Make target that points to new compose path.
4. Keep backward-compatible root `docker-compose.yml` wrapper for one transition window.
5. Gate: services boot and health checks pass.

## Phase 5: Compatibility Removal (final hardening)

1. Remove legacy wrappers after all imports updated.
2. Remove dual-read path fallbacks.
3. Update docs and operational scripts to new structure only.
4. Gate: full tests + startup diagnostics + smoke tests pass.

---

## 5) Step-Level Safety Checklist (before moving anything)

For every file/module move, answer:

1. What imports this file?
2. What env vars/config does it use?
3. What filesystem paths are hardcoded?
4. Any Docker bind mounts referencing this path?
5. Will this change user workflow or scripts?

If any answer is unclear, stop and map dependencies before moving.

---

## 6) Rollback Strategy

1. Keep changes in small isolated commits (one logical unit each).
2. Rollback by reverting one commit, not by manual file surgery.
3. Never delete old data path until copied + verified.
4. Keep compatibility wrappers until post-cutover validation window is complete.

---

## 7) Immediate Next Execution Unit

Recommended next unit (smallest safe move):

1. Implement `src/shared/paths.py` and `src/shared/services.py`.
2. Wire `api/file_utils.py`, `api/app.py`, `api/validator.py`, and `pte_core/asr/*` to read constants from there.
3. Keep existing directory structure untouched.
4. Run full tests and smoke checks.

