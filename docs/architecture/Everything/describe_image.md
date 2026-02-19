# Describe Image Architecture

## 1. Overview

The **Describe Image** feature evaluates a student's spoken description of an image (graph, chart, map) against a reference description.

- **Input**: Audio recording + Image ID
- **Output**: 0-90 Total Score + Content / Pronunciation / Fluency sub-scores + Detailed Feedback

---

## 2. Real PTE vs. Our Implementation

| Feature | Real PTE System (Pearson) | Our Local Agent |
| :--- | :--- | :--- |
| **Logic** | **Black Box**: Uses massive datasets of human-graded responses. | **Hybrid**: AI for meaning + MFA for pronunciation + Code for structure. |
| **Reference** | Statistical average of thousands of answers. | Single high-quality reference text per image. |
| **Scoring** | Latent Semantic Analysis (LSA). | **Sentence Embeddings** + MFA Phoneme Analysis + Rules. |
| **Infrastructure** | Cloud Servers. | **Local CPU/GPU**. |

---

## 3. Scoring System — APEuni-Style (Content / Pronun / Fluency)

All three sub-scores are reported on a **0–90 scale**, matching APEuni's layout.

### A. Content Score (0–90) — "Did you say the right things?"

Combines two signals:

| Signal | Weight in total | Points |
|---|---|---|
| Semantic Match (`all-MiniLM-L6-v2` cosine similarity) | 26.7% | 0–24 pts |
| Keyword Coverage (set matching) | 13.3% | 0–12 pts |

- **Semantic Match**: Encodes both reference and student text as vectors, computes cosine similarity (0–1), scales to 24 pts.
- **Keyword Coverage**: Checks what fraction of the image's key words (e.g., "bar chart", "Q1", "upward trend") appear in the transcription.
- Combined 0–36 pts → scaled to **0–90** for display.

### B. Pronunciation Score (0–90) — "Did you say it correctly?"

- **Source**: MFA (Montreal Forced Aligner) word-level alignment, run on the student's audio.
- **Per-word accuracy**: Each word gets an `accuracy_score` (0–100) based on phoneme-level matching.
- **Aggregation**: Average accuracy across all words → scaled to **0–90**.
- Inserted (extra) words are penalised as 0% accuracy.
- Contributes **30%** to the total score (0–27 pts internally).

### C. Fluency Score (0–90) — "Did you speak smoothly and at the right length?"

Combines two signals:

| Signal | Weight in total | Points |
|---|---|---|
| Structure Analysis (Regex) | 15% | 0–13.5 pts |
| Length Ratio | 15% | 0–13.5 pts |

- **Structure**: Checks for intro ("The chart shows…"), trend words ("increase", "highest"), and conclusion ("Overall…").
- **Length Ratio**: Compares student word count to reference word count. Optimal range: 60%–150%.
- Combined 0–27 pts → scaled to **0–90** for display.

### D. Total Score (0–90)

```
Total = Content_pts(0-36) + Pronun_pts(0-27) + Fluency_pts(0-27)
      = max 90 pts
```

---

## 4. Pipeline (Request Flow)

```
Browser → POST /describe-image/submit
    → ffmpeg converts audio to 16kHz WAV
    → Background thread:
        1. Whisper ASR → transcription text
        2. MFA align_and_validate(audio, text) → word-level phoneme data
        3. evaluate_description(image_id, text, mfa_words)
            ├── SentenceTransformer → content_score
            ├── keyword_coverage() → keyword contribution
            ├── compute_pronunciation_score(mfa_words) → pronun_score
            └── check_structure() + length_ratio → fluency_score
    → Poll /describe-image/status/<job_id>
    → Display results
```

---

## 5. Known Limitations & Future Work

| Area | Current | Future |
|---|---|---|
| **Fluency** | Length ratio + structure regex | Real pause detection from MFA silence intervals |
| **Pronunciation** | Word-level phoneme accuracy | Sentence-level prosody / intonation |
| **Reference** | Single reference text | Multiple reference texts averaged |
| **Images** | 6 images | Expandable via `data/reference/describe_image/references.json` |

---

## 6. Stack Summary

| Component | Technology |
|---|---|
| Language | Python 3.9+ |
| Framework | Flask |
| ASR | Whisper (local) |
| Alignment | MFA (Montreal Forced Aligner) |
| Semantic Model | `all-MiniLM-L6-v2` via `sentence-transformers` (~80MB, local) |
| NLP Tools | `scipy` (cosine distance), `re` (regex) |
| Model Loading | **Eager** — loaded at import time to avoid thread-context issues |
