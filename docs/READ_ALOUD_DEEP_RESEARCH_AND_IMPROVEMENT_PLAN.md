# Read Aloud Deep Research and Improvement Plan

Date: February 23, 2026

## 1) Executive verdict (honest)

The current Read Aloud system is **not production-grade yet** for fair scoring, even though it has a strong base architecture.

What is good:
- End-to-end pipeline exists (ASR + MFA + word-level output + UI).
- Accent-aware phoneme scoring exists.
- Async streaming progress is implemented.
- The system saves artifacts, which makes debugging possible.

What is not good enough yet:
- **Latency is high** (typically ~45-90 seconds for Read Aloud attempts in local saved runs).
- **Stress scoring is currently broken for many words** due phone-set mismatch (IPA vs ARPA assumptions).
- **Pause scoring is frequently invalid** due anchor logic and status coupling.
- **Repeated words are often mapped to the first occurrence**, causing wrong timings and wrong scoring.
- UI feedback is still too technical and not learner-friendly.

Bottom line: your intuition is correct. The system needs targeted redesign for speed + correctness, not just more hardware.

---

## 2) Scope and method

This study combines:
- Code audit of active runtime path (`/check_stream` -> `api/validator.py`).
- Local evidence from saved attempt artifacts under `data/user_uploads/read_aloud_*/analysis/check_stream_result.json`.
- External references from official PTE and MFA documentation.

Primary code paths audited:
- `api/app.py:1047`
- `api/validator.py:684`
- `pte_core/scoring/stress.py:10`
- `pte_core/scoring/accent_scorer.py:103`
- `api/templates/index.html:780`
- `docker/asr-grammar/app.py:88`
- `docker/phoneme-service/phoneme_model.py:22`

---

## 3) Current system flow (as implemented)

1. Frontend posts audio to `/check_stream` (`api/app.py:1047`).
2. Backend converts audio with ffmpeg (`api/app.py:1065`).
3. ASR transcript + word timestamps are fetched (`api/validator.py:703`).
4. Content diff is computed via `difflib.SequenceMatcher` (`api/validator.py:273`).
5. MFA runs via `docker run ... mfa align ...` (`api/validator.py:399`) with `--num_jobs 1` (`api/validator.py:412`).
6. Word-level analysis runs through `analyze_word_pronunciation` (`api/validator.py:487`).
7. Stress is computed by energy heuristic (`pte_core/scoring/stress.py:10`).
8. Pause scoring is performed at punctuation (`api/validator.py:947`, `pte_core/pause/pause_evaluator.py:15`).
9. UI renders statuses and modal details (`api/templates/index.html:780`, `api/templates/index.html:1050`).

---

## 4) Measured baseline from your local saved runs

Dataset sampled: `17` Read Aloud attempts with saved `check_stream_result.json` and WAV timestamps.

Latency (approx = `result_mtime - wav_mtime`):
- Count: `17`
- Mean: `55.7s`
- Median: `54s`
- P90: `90s`
- Range: `4s` to `91s`

Interpretation:
- Typical user wait is around 1 minute.
- Worst cases are ~1.5 minutes.
- A few very fast cases correspond to fallback behavior (not full phoneme analysis).

Other observed metrics:
- `asr_only` fallback in `4/17` attempts.
- Stress entries with `"No vowels detected"`: `523/627` (`83.4%`).
- Pause events: `81/81` were `missed_pause` with null timing bounds in sampled runs.
- Repeated words often have duplicated timestamps (e.g., repeated `fall` sharing identical start/end), indicating first-occurrence matching.

---

## 5) Critical issues (ranked)

### P0. Stress algorithm and phone set mismatch

Evidence:
- Stress code expects ARPA-like vowels (`AA, AE, ...`) (`pte_core/scoring/stress.py:43`).
- MFA TextGrid in saved runs contains IPA-like phones (e.g., `ə`, `ɪ`, `d̪`).
- Result: frequent `"No vowels detected"` and stress score collapse.

Impact:
- Incorrectly lowers pronunciation outcomes.
- Cascades into mispronounced decisions because combined score uses stress (`api/validator.py:665`).

### P0. Repeated words mapped to first occurrence

Evidence:
- Word match picks first identical token and breaks (`api/validator.py:503` to `api/validator.py:506`).

Impact:
- Wrong timestamps for repeated words.
- Wrong phones, stress, and playback snippets.

### P0. Pause scoring tied to `status == correct`

Evidence:
- Pause anchors only consider previous/next words with status `correct` (`api/validator.py:957`, `api/validator.py:966`).

Impact:
- If words become `mispronounced`, punctuation pauses get null bounds.
- Creates false `missed_pause` penalties at scale.

### P1. UI/backend status mismatch for pause

Evidence:
- Backend emits `missed_pause` (`pte_core/pause/pause_evaluator.py:62`).
- Frontend checks `missing_pause` (`api/templates/index.html:831`).

Impact:
- Missed pauses may not render correctly in UI hints.

### P1. Claimed parallel analysis is effectively sequential

Evidence:
- Comment says parallel; executor has `max_workers=1` (`api/validator.py:883`, `api/validator.py:902`).
- Per-word timeout up to 45s can snowball (`api/validator.py:911`).

Impact:
- Large latency under load and long passages.

### P1. MFA launched as fresh Docker container per request

Evidence:
- `docker run --rm ... mfa align ...` each request (`api/validator.py:399`).
- Also limited to `--num_jobs 1` (`api/validator.py:412`).

Impact:
- High cold-start and alignment runtime.

### P1. Scoring fallback defaults to perfect on failures

Evidence:
- If no phones or exception, accuracy defaults to 100 (`api/validator.py:610` to `api/validator.py:618`).

Impact:
- Can hide genuine pronunciation errors.

### P2. ASR timestamp conversion uses fixed 40ms assumption

Evidence:
- `start_offset * 0.04`, `end_offset * 0.04` (`docker/asr-grammar/app.py:143`).

Impact:
- Timing drift risk if model frame assumptions differ.

### P2. Potential runtime artifact bloat

Evidence:
- Cleanup is commented out for MFA runtime dirs (`api/validator.py:1044` to `api/validator.py:1050`).

Impact:
- Storage growth and potential I/O degradation over time.

### P2. ASR fallback to pseudo transcript in production path

Evidence:
- On ASR failure, returns pseudo content (`pte_core/asr/voice2text.py:51`).

Impact:
- Silent quality degradation and trust risk.

---

## 6) What “stress” means in PTE and how to implement it correctly

From official PTE materials:
- Read Aloud contributes to content, pronunciation, and oral fluency scoring.
- Pronunciation includes vowels, consonants, and stress.
- Oral fluency includes rhythm, phrasing, stress, and intonation.

References:
- PTE Academic Score Guide (PDF): https://www.pearsonpte.com/-/media/pte/PDF/PTEA_ScoreGuide.pdf
- PTE Automated Scoring White Paper (Pearson): https://www.pearsonpte.com/content/dam/pearsonpte/pte/pdf/White-paper-How-the-PTE-Academic-Automated-Scoring-System-works.pdf

Implementation guidance:
- Stress should be computed on **syllable prominence** (energy + duration + pitch movement), not only dictionary stress digits.
- Handle both ARPA and IPA consistently before stress analysis.
- Stress should be a **bounded contributor** to pronunciation, not a dominant failure trigger if phone recognition is strong.

Recommended formula per word:
- `phone_accuracy` in `[0,100]`
- `stress_accuracy` in `[0,100]`
- `word_pron_score = 0.85 * phone_accuracy + 0.15 * stress_accuracy`

Reason:
- PTE includes stress, but intelligibility should still be primarily phone-driven.

---

## 7) Accent mapping strategy (practical)

Current behavior:
- UI accent selection controls model and scorer mapping (`api/validator.py:868`).
- `US_ARPA` and `US_MFA` map to `Non-Native English` scorer profile.

Suggested strategy:
1. Keep user-select accent as explicit primary profile.
2. Internally evaluate a secondary neutral profile in background for robustness.
3. If score gap is very large, flag accent-profile uncertainty (do not harshly penalize).
4. Never optimize for native-likeness; optimize for intelligibility + consistency.

Suggested mapping:
- `US_ARPA`, `US_MFA` -> `General English` (rename from `Non-Native English` for UX clarity)
- `Indian` -> `Indian English`
- `Nigerian` -> `Nigerian English`
- `UK` -> `United Kingdom`
- `NonNative` -> `General English (Broad tolerance)`

---

## 8) Performance plan (time + compute)

### Phase A (1-3 days, fast wins)

1. Fix stress phone normalization first.
- Normalize MFA phones to canonical set before vowel detection.
- Accept IPA vowels directly.

2. Fix repeated-word alignment.
- Match by sequence index / overlap window, not first lexical match.

3. Decouple pause anchoring from `status == correct`.
- Use nearest timestamped spoken tokens instead.

4. Eliminate fake-perfect fallback scores.
- Replace default 100 with neutral/unknown and confidence drop.

5. Remove unused dictionary loading in hot path.
- `dictionaries` in `align_and_validate_gen` are loaded but not used.

6. Cache TextGrid parse once per request.
- Parse `base_tg` once and pass structured arrays to per-word analyzer.

Expected outcome:
- Accuracy consistency improves immediately.
- Latency typically improves 10-25%.

### Phase B (1-2 weeks, structural speedups)

1. Replace per-request `docker run` MFA with persistent worker process/service.
- Avoid repeated container boot overhead.

2. Tune MFA concurrency safely.
- Make `--num_jobs` configurable by CPU cores (start 2-4).

3. Redesign word analysis execution model.
- Keep thread-unsafe parts isolated.
- Parallelize pure-Python scoring where safe.

4. Add caching key:
- `cache_key = hash(audio_bytes + reference_text + accent + model_versions)`

Expected outcome:
- Bring median latency from ~54s toward ~20-35s on same hardware.

### Phase C (advanced)

1. Two-stage response UX:
- Stage 1 (<5s): content + rough fluency.
- Stage 2 (background): full phoneme + stress detail.

2. Optional distilled lightweight aligner for near-real-time feedback.

3. Batch phoneme inference endpoint (single audio decode, multi-segment inference).

Expected outcome:
- Much better perceived responsiveness without losing depth.

---

## 9) Accuracy plan (scoring redesign)

Separate score channels clearly:
- `content_score`: reference coverage only (omissions/insertions/substitutions).
- `pronunciation_score`: phone + stress only.
- `fluency_score`: pauses + speech rate + hesitation.

Do not mix punctuation and pronunciation statuses into one `correct/total` number for UI headline.

Proposed displayed summary:
- Content: `x/90`
- Pronunciation: `x/90`
- Fluency: `x/90`
- Overall: weighted aggregate

This aligns better with PTE user expectations and avoids misleading “accuracy %” outputs.

---

## 10) UX: how to explain stress simply (non-technical)

Current UI shows patterns like `10 -> 01` (`api/templates/index.html:1068`), which is technical.

Use this instead:
- “You stressed the wrong part of this word.”
- “Try saying **CAN-ada** (stress on first part), not **ca-NA-da**.”
- “Keep this syllable stronger: **TEM**-perature.”

Per-word card recommendation:
- Label: `Sound`, `Stress`, `Flow` (not ARPA/IPA by default)
- Show one short fix instruction
- Optional “Show technical details” expandable section

This will reduce cognitive load and improve learner actionability.

---

## 11) Implementation backlog (prioritized)

P0 (do now):
- Stress normalization fix.
- Repeated-word alignment fix.
- Pause anchor logic fix.
- Remove fake-perfect fallback scoring.
- Fix `missed_pause` vs `missing_pause` UI mismatch.

P1 (next):
- Cache parsed TextGrid and G2P resources per request/session.
- Remove unused dict loading from runtime path.
- Expose separate content/pronunciation/fluency scores in API contract.

P2 (structural):
- Persistent MFA worker/service.
- Configurable MFA `num_jobs`.
- Add result caching and telemetry (p50/p90 by accent and passage length).

---

## 12) Validation and rollout metrics

Latency SLO:
- p50 < 25s
- p90 < 45s

Quality gates:
- Stress false-negative rate down by >50% on annotated set.
- Pause null-bound events reduced to near 0.
- Duplicate-timestamp repeated-word artifacts reduced to near 0.

Safety:
- If ASR/MFA fails, return explicit degraded mode flags (never pseudo-silent fallback as normal result).

A/B rollout:
- Compare old vs new on same corpus.
- Require no regression in content agreement and human-review intelligibility judgment.

---

## 13) External references used

1. Pearson PTE Academic Score Guide (official PDF)
- https://www.pearsonpte.com/-/media/pte/PDF/PTEA_ScoreGuide.pdf

2. Pearson White Paper: How the PTE Academic Automated Scoring System Works
- https://www.pearsonpte.com/content/dam/pearsonpte/pte/pdf/White-paper-How-the-PTE-Academic-Automated-Scoring-System-works.pdf

3. MFA documentation (alignment command, options)
- https://montreal-forced-aligner.readthedocs.io/en/v3.3.6/user_guide/workflows/alignment.html

4. MFA documentation (phone set notes: ARPA/IPA handling)
- https://montreal-forced-aligner.readthedocs.io/en/v3.3.8/user_guide/configuration/phone_set.html

