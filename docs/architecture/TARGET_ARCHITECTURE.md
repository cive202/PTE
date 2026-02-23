# Target Architecture: Production Structure

## 1) Design Goals

1. Keep all current features and API contracts unchanged.
2. Separate runtime code, static reference data, user-generated data, and infra config.
3. Isolate orchestration concerns (API) from domain logic (scoring/alignment).
4. Make migration incremental with compatibility shims.
5. Reduce hardcoded paths and service URLs through centralized config.

---

## 2) Proposed Directory Structure

```text
pte/
├── src/
│   ├── api/                       # Flask app, routes, request/response contracts
│   ├── core/                      # Domain logic (ASR client, MFA orchestration, scoring, pause)
│   ├── services/                  # Service clients and adapters
│   │   ├── asr_grammar_client.py
│   │   ├── phoneme_client.py
│   │   └── mfa_runner.py
│   ├── modules/                   # Task modules
│   │   ├── read_aloud/
│   │   ├── repeat_sentence/
│   │   ├── describe_image/
│   │   └── retell_lecture/
│   └── shared/                    # Common utils, config, schemas
├── data/
│   ├── reference/                 # Static content used by tasks
│   │   ├── read_aloud/
│   │   ├── repeat_sentence/
│   │   ├── describe_image/
│   │   └── retell_lecture/
│   ├── user_uploads/              # User audio + paired user text
│   ├── processed/
│   │   ├── mfa_runs/
│   │   └── scoring_cache/
│   ├── models/                    # Dictionaries and acoustic models
│   │   ├── mfa/
│   │   └── local/
│   └── archive/                   # Historical/manual artifacts
├── docker/
│   ├── asr-grammar/
│   ├── phoneme-service/
│   └── compose/
├── scripts/                       # Admin and utility scripts
├── tests/
│   ├── contracts/
│   ├── integration/
│   └── unit/
├── docs/
│   ├── architecture/
│   ├── operations/
│   └── migration/
└── config/
    ├── app.yaml
    ├── paths.yaml
    └── services.yaml
```

---

## 3) Migration Mapping (Old -> New)

## 3.1 Runtime code

1. `api/` -> `src/api/`
2. `pte_core/` -> `src/core/`
3. `read_aloud/` -> `src/modules/read_aloud/`
4. `repeat_sentence/` -> `src/modules/repeat_sentence/`
5. `pte_tools.py` -> `src/shared/pte_tools.py`

## 3.2 Data

1. `data_2/read_aloud_references.json` -> `data/reference/read_aloud/references.json`
2. `data_2/repeat_sentence_references.json` -> `data/reference/repeat_sentence/references.json`
3. `data_2/repeat-sentence-audio/` -> `data/reference/repeat_sentence/audio/`
4. `data_2/image_references.json` + `data_2/images/` -> `data/reference/describe_image/`
5. `data_2/lecture_references.json` + `data_2/lectures/` -> `data/reference/retell_lecture/`
6. `corpus/` (active user files) -> `data/user_uploads/`
7. `PTE_MFA_TESTER_DOCKER/data/run_*` -> `data/processed/mfa_runs/<run_id>/input/`
8. `PTE_MFA_TESTER_DOCKER/data/output_*` -> `data/processed/mfa_runs/<run_id>/output/<accent>/`
9. `PTE_MFA_TESTER_DOCKER/*_model/*` dict/zip -> `data/models/mfa/<accent>/`
10. `PTE_MFA_TESTER_DOCKER/output_*` + `old_data/` -> `data/archive/mfa_legacy/`

## 3.3 Docker/infrastructure

1. `PTE_ASR_GRAMMAR_DOCKER/` -> `docker/asr-grammar/`
2. `wav2vec2_service/` -> `docker/phoneme-service/`
3. `docker-compose.yml` -> `docker/compose/docker-compose.yml`

## 3.4 Documentation and plans

1. `README_STARTUP.md` -> `docs/operations/startup.md`
2. `INSTALL_MFA.md` -> `docs/operations/mfa_install.md`
3. `.trae/documents/*` -> `docs/migration/history/` (optional archival import)

---

## 4) Organizational Rationale

1. **`src/` split by responsibility**:
   keeps HTTP surface, core domain logic, and task-specific modules independent.
2. **`data/` split by lifecycle**:
   reference (immutable), uploads (sensitive), processed outputs (derived), models (versioned), archive (legacy).
3. **`docker/` centralization**:
   isolates infra from application runtime code and simplifies deployment ownership.
4. **`config/` centralization**:
   replaces hardcoded paths/URLs with environment-specific settings.
5. **`docs/` centralization**:
   makes architecture and operations discoverable in one place.

---

## 5) Risks and Mitigations

## 5.1 Import breakage during moves

- **Risk**: existing imports (`from api...`, `from pte_core...`) fail.
- **Mitigation**: add compatibility packages (`api/`, `pte_core/`, `read_aloud/`) that re-export from `src/...` until full cutover.

## 5.2 Hardcoded path regressions

- **Risk**: file I/O fails after directory moves.
- **Mitigation**: introduce `src/shared/paths.py` first; switch all runtime path joins to named constants/env-config.

## 5.3 Docker volume mount mismatch

- **Risk**: MFA/ASR services cannot access expected files.
- **Mitigation**: migrate compose and bind mounts in one step with explicit smoke checks for `/health`, `/asr`, `/phonemes`, and MFA run.

## 5.4 Data migration errors

- **Risk**: user or model data lost/misplaced.
- **Mitigation**: copy-first migration, checksum verification, no destructive deletion until post-cutover validation.

## 5.5 API contract drift

- **Risk**: frontend breaks due changed response schema.
- **Mitigation**: keep route signatures identical; enforce contract tests (`tests/test_api_contracts.py`) at each migration step.

## 5.6 Runtime compatibility across Python versions

- **Risk**: dependency runtime mismatch (example: `panphon` behavior).
- **Mitigation**: pin supported Python version in docs/CI and keep tests with stubs for optional heavy dependencies.
