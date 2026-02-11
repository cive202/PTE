# Architecture Analysis: Current PTE System

## 0) What Confuses a New Developer Most

If a new developer joins tomorrow, the most confusing points are:

1. **Mixed responsibilities in `api/validator.py`**:
   one file handles ASR orchestration, MFA Docker execution, TextGrid parsing, phoneme scoring, pause scoring, and response shaping.
2. **Multiple data roots with overlapping names**:
   `corpus/`, `PTE_MFA_TESTER_DOCKER/data/`, and `PTE_MFA_TESTER_DOCKER/output_*` all contain audio/text/alignment artifacts with different lifecycle rules.
3. **Two "engines" coexisting**:
   production web path uses `api/app.py` + `api/validator.py`, while reusable pipelines live in `pte_core/`, `read_aloud/`, and `repeat_sentence/` with partial overlap.
4. **Docker is split by function and by history**:
   `docker-compose.yml` defines ASR/Grammar and phoneme services, but MFA runs through ad-hoc `docker run` calls from Python code.
5. **Hardcoded paths and endpoints**:
   several modules assume local paths (`corpus`, `data_2`, `PTE_MFA_TESTER_DOCKER`) and localhost service URLs.

---

## 1) Data Flow Mapping

## 1.1 Main user-audio flow (Read Aloud and Repeat Sentence)

1. Client records/uploads audio to Flask endpoint (`/check`, `/check_stream`, `/save`).
2. Flask stores temporary/user files in `corpus/` via `api/file_utils.py`.
3. Audio is converted to 16k mono WAV in `api/app.py` (`convert_to_wav`).
4. For scoring:
   - `api/app.py` calls `api.validator.align_and_validate*`.
   - `api/validator.py` calls ASR via `pte_core.asr.voice2text` (`http://localhost:8000/asr`).
5. For MFA:
   - `api/validator.py` copies input WAV/TXT into `PTE_MFA_TESTER_DOCKER/data/run_<id>/`.
   - Executes MFA container (`mmcauliffe/montreal-forced-aligner`) with mounted `PTE_MFA_TESTER_DOCKER:/data`.
   - Reads `input.TextGrid` from `PTE_MFA_TESTER_DOCKER/data/output_<accent>_<id>/`.
6. Word-level analysis combines:
   - content diff (reference vs transcript),
   - MFA phones/TextGrid timing,
   - fallback phoneme service (`http://localhost:8001/phonemes`) when needed.
7. Result JSON/NDJSON returned; some temp files are cleaned, but many MFA run/output folders remain.

## 1.2 Describe Image / Retell Lecture flow

1. Upload audio to `/describe-image/submit` or `/retell-lecture/submit`.
2. Save WAV in `corpus/`.
3. Transcribe via ASR service.
4. Create temporary transcript text file (next to WAV).
5. Run `align_and_validate` for phoneme/timing details.
6. Run task-specific evaluator against references in `data_2/`.
7. Return score + transcription details + MFA word timing/status.

## 1.3 Reference vs generated content

- **Reference/static content**: `data_2/` JSON, lecture audio, repeat-sentence audio, images.
- **User-submitted and transient content**: `corpus/` and `PTE_MFA_TESTER_DOCKER/data/run_*`.
- **Derived/processed alignment outputs**: `PTE_MFA_TESTER_DOCKER/data/output_*` and legacy `PTE_MFA_TESTER_DOCKER/output_*`.

## 1.4 Entry points

- **Web/API entrypoint**: `api/app.py` (Flask, port 5000).
- **Container services**:
  - `PTE_ASR_GRAMMAR_DOCKER/app.py` (FastAPI, port 8000; `/asr`, `/grammar`, `/health`).
  - `wav2vec2_service/app.py` (Flask, port 8001; `/phonemes`, `/health`).
- **Orchestrator**: `docker-compose.yml` for the 8000/8001 services.
- **MFA execution**: invoked from Python (`api/validator.py`) via `docker run` on demand.
- **CLI-like scripts**: `generate_dict.py`, `pte_tools.py`, and module `__main__` blocks.

---

## 2) User Data Locations and Lifecycle

## 2.1 All observed user-data storage locations

1. `corpus/`
   - Web uploads, converted WAVs, paired `.txt`, temp uploads.
   - Mix of current run files and historical artifacts.
2. `PTE_MFA_TESTER_DOCKER/data/run_<id>/`
   - Per-run MFA input copies (`input.wav`, `input.txt`).
3. `PTE_MFA_TESTER_DOCKER/data/output_<accent>_<id>/`
   - Per-run MFA outputs (`input.TextGrid`, alignment CSV).
4. `PTE_MFA_TESTER_DOCKER/output_*`
   - Legacy/manual batch outputs (`output_us`, `output_indian`, etc.).
5. `PTE_MFA_TESTER_DOCKER/old_data/`
   - Historical samples.

## 2.2 Why data appears in both `corpus/` and `PTE_MFA_TESTER_DOCKER/`

- They are not pure duplicates:
  - `corpus/` is application-facing upload/transient working storage.
  - `PTE_MFA_TESTER_DOCKER/data/` is Docker-mounted MFA workspace and output location.
- The same logical attempt is copied from `corpus/` into MFA workspace for alignment.
- Missing retention policy means both locations accumulate files over time.

## 2.3 User data lifecycle (current)

1. Upload saved to `corpus/` temp.
2. Converted WAV + reference text written to `corpus/`.
3. For MFA, copied into `PTE_MFA_TESTER_DOCKER/data/run_<id>/`.
4. MFA output written into `PTE_MFA_TESTER_DOCKER/data/output_<accent>_<id>/`.
5. Some `corpus/` temps removed; many MFA folders and older files are not deleted.
6. Historical files persist indefinitely unless manually cleaned.

---

## 3) Docker Services Inventory

## 3.1 Active services and purpose

1. **`asr-grammar`** (`PTE_ASR_GRAMMAR_DOCKER`, port 8000)
   - NeMo Parakeet ASR (`/asr`).
   - LanguageTool grammar checking (`/grammar`).
2. **`wav2vec2-service`** (`wav2vec2_service`, port 8001)
   - CPU phoneme recognition (`/phonemes`) for segment-level phone extraction.
3. **MFA container** (`mmcauliffe/montreal-forced-aligner`, ad hoc)
   - Not managed by compose.
   - Spawned from `api/validator.py` as needed.

## 3.2 Why separate `PTE_ASR_GRAMMAR_DOCKER` and `wav2vec2_service`

- Current split is intentional by compute/model profile:
  - ASR + grammar stack is heavy and different from wav2vec2 phoneme model stack.
  - Independent containers allow separate restart/deploy and avoid cross-library conflicts.
- However, orchestration is incomplete because MFA is outside compose.

## 3.3 Consolidation assessment

- Keep ASR/grammar and phoneme as separate services in near term (good operational boundary).
- Candidate consolidation is not ASR+phoneme; it is **MFA orchestration** into managed service tooling (not ad-hoc shell execution).

---

## 4) Module Dependencies

## 4.1 High-level dependency graph

- `api/app.py` -> `api/validator.py`, task evaluators, file utils.
- `api/validator.py` -> `pte_core` (ASR, pause, phoneme, scoring) + `read_aloud.alignment`.
- `pte_core/asr/voice2text.py` -> ASR container endpoint.
- `pte_core/asr/phoneme_recognition.py` -> wav2vec2 container endpoint.
- `repeat_sentence/pte_pipeline.py` and `read_aloud/pte_pipeline.py` -> `pte_tools.py`.
- `pte_tools.py` -> both `pte_core` and `read_aloud` modules.

## 4.2 Coupling and boundary issues

1. `pte_core` imports `read_aloud` in some paths (`pte_core/mfa/pronunciation.py`, `pte_core/pause/rules.py`).
2. `api/validator.py` depends on both `pte_core` and `read_aloud`.
3. Global path mutation (`sys.path.insert`) appears in multiple modules.

## 4.3 Circular dependency risk

- No hard import crash observed in tests, but architecture has **directional leakage**:
  `core` layer references task-specific `read_aloud` layer, which is opposite of clean layering.

---

## 5) Critical Integration Points (must not break)

1. **MFA alignment workflow**
   - `align_and_validate_gen` copy-in + `docker run` + TextGrid readback.
2. **ASR pipeline**
   - `pte_core.asr.voice2text` contract (`text`, `word_timestamps`) from `http://localhost:8000/asr`.
3. **Phoneme pipeline**
   - `call_phoneme_service` contract from `http://localhost:8001/phonemes`.
4. **Public API routes**
   - `/check`, `/check_stream`, `/check/status/<job_id>`.
   - `/speaking/read-aloud/get-topics`, `/speaking/repeat-sentence/get-task`.
   - `/api/grammar`, describe-image and retell-lecture submit/status routes.
5. **Data files required at runtime**
   - `data_2/*_references.json`, images, lecture and repeat-sentence media.

---

## 6) Mystery Resolution Notes

## 6.1 Why user data in multiple places?

- `corpus/` = app-level uploads/transient files.
- `PTE_MFA_TESTER_DOCKER/data/` = MFA run workspace + generated output per run.
- `PTE_MFA_TESTER_DOCKER/output_*` = older/manual outputs from prior scripts.
- So this is a mix of active runtime paths and historical artifacts, not one canonical strategy.

## 6.2 Multiple ASR implementations?

- `pte_core/asr/voice2text.py` is the active integration used by web/API validator.
- `read_aloud/asr/pseudo_voice2text.py` and `pte_core/asr/pseudo_voice2text.py` provide fallback/mock timestamp data and legacy pipeline support.
- Consolidation opportunity exists, but pseudo fallback currently prevents hard failure when ASR service is unavailable.

## 6.3 Docker service confusion

- `PTE_ASR_GRAMMAR_DOCKER` and `wav2vec2_service` are both active microservices used by runtime code.
- MFA is separate: triggered ad hoc from Python and not represented as a persistent service.

## 6.4 What is `.trae/`?

- `.trae/documents/*` are planning/handover notes (markdown).
- No runtime imports/config reads from `.trae` were found.

---

## 7) Risks in Current Architecture

1. Data growth and privacy risk: no strict retention policy for user audio/transcripts/alignment outputs.
2. Operational fragility: runtime depends on shelling out to Docker from request flow.
3. Hardcoded URLs/paths reduce portability and environment parity.
4. Broad module coupling increases regression risk during refactors.
5. Heavy services have startup and dependency drift risk (NeMo, LanguageTool, panphon).

