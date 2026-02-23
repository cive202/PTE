# Summarize Written Text + Write Essay + Write Email

Deep-research implementation guide for adding these three writing features in this project.

## Why this document

You asked for:

1. What these features are.
2. How to implement them in a reliable way.
3. How others implement similar scoring systems.
4. Source-backed guidance you can present inside company discussions.

This file is written in simple technical terms but with production-level detail.

## 1) What these tasks are (official scoring behavior)

Based on current publicly available Pearson guides:

- `Summarize Written Text (SWT)` and `Write Essay` are PTE Academic tasks scored with partial credit using rubric traits.
- In `PTE Core`, `Write Email` is the writing production task replacing `Write Essay` in the speaking/writing section.
- PTE Core speaking/writing section is `46-67` minutes overall and includes `2-3` Write Email items.
- PTE Core `Write Email` is trait-scored with these max points:
  - `Content`: 3
  - `Formal requirements`: 2
  - `Grammar`: 2
  - `Vocabulary`: 2
  - `Spelling`: 2
  - `Email conventions`: 2
- PTE Core `Formal requirements` word-band logic is explicit:
  - `2`: 50-120 words (and includes salutation, purpose statement, closing)
  - `1`: 30-49 or 121-150 words (and includes only two of those structural elements)
  - `0`: fewer than 30 words, more than 150 words, or response is not an email
- PTE Core guide also states: if `Content = 0` or `Formal requirements = 0`, no points are awarded for Grammar/Vocabulary/Spelling.
- Pearson describes automated scoring for Write Email using Intelligent Essay Assessor (IEA) and Knowledge Analysis Technologies (KAT) engine components trained on expert-scored responses.

Important:

- Rubrics can change over time. Do not hardcode constants in business logic.
- Keep trait names, score bands, and rules in versioned config files keyed by product and task:
  - `PTE Academic / SWT`
  - `PTE Academic / Essay`
  - `PTE Core / Write Email`

## 2) What a reliable implementation looks like

Reliable here means:

- It follows official form rules exactly (word count, sentence/email constraints, prompt relevance).
- It scores by rubric traits, not one opaque "overall AI score".
- It has measurable agreement with trained human raters.
- It detects template/memorized/off-topic responses.
- It is explainable enough for audits and client demos.

For Write Email specifically, reliability also means:

- It checks audience and purpose fit (register, tone, structure).
- It treats email structure as a scored requirement, not optional style.

## 3) Recommended architecture for this repo

Use a `hybrid scoring pipeline` (rules + NLP models + calibration), not a single model.

### Request flow

1. Receive `exam_type`, `task_type`, prompt, response, metadata.
2. Preprocess text (normalize spaces/punctuation, sentence split, tokenize words).
3. Load rubric config by version (`rubrics/<exam>/<task>/<version>.yaml`).
4. Run hard rule gates (form + minimum validity checks).
5. Run trait scorers.
6. Calibrate trait outputs to rubric scales.
7. Produce:
   - trait scores
   - total score
   - short feedback lines per trait
   - confidence flags / review flags

### Suggested services/modules

- `task_router.py`
- `form_gate.py`
- `content_scorer.py`
- `coherence_scorer.py`
- `language_scorer.py` (grammar + vocabulary + spelling)
- `email_conventions_scorer.py`
- `template_detector.py`
- `calibration.py`
- `explanations.py`
- `rubrics/<exam>/<task>/<version>.yaml`

## 4) SWT implementation blueprint

SWT is not a free summary task. It is a constrained one-sentence academic summary.

### A. Form gate (must run first)

- Exactly one complete sentence.
- Word count boundary from rubric (`5-75` in current guide copy).
- Reject all-caps, bullet-only, or malformed response patterns.

If `Form = 0`, return early with no additional trait points (same scoring principle used in official guide examples).

### B. Content scoring

Use a two-part method:

- `Coverage`: does the summary include main ideas from source text?
- `Faithfulness`: does it avoid distortion/hallucination?

Practical way:

1. Extract top key ideas from source passage (sentence ranking + embedding clustering).
2. Score semantic overlap between response and key ideas (SBERT cosine + keyword overlap).
3. Penalize unsupported claims not grounded in source.

### C. Grammar + vocabulary

- Grammar error density and severity.
- Lexical appropriateness and variety.
- Paraphrasing quality (avoid raw copying of long spans).

### D. Feedback output

Return 2-4 short, actionable comments:

- missed core idea
- sentence structure issue
- weak paraphrasing / over-copying

## 5) Write Essay implementation blueprint (PTE Academic)

Essay scoring should be `analytic` (trait-level), then aggregated.

### A. Form and prompt relevance gate

- Word count band check.
- Prompt relevance check (embedding similarity + contradiction/off-topic signal).
- Template/memorized material detector.

### B. Trait scorers

Implement separate models/features for each trait:

- `Content`: prompt coverage, claim relevance, example relevance.
- `Development/Structure/Coherence`: argument flow, paragraph logic, transitions.
- `Grammar`: syntactic correctness, agreement, tense consistency, sentence well-formedness.
- `Vocabulary / Linguistic range`: lexical diversity + precision, but penalize forced rare-word stuffing.
- `Spelling`: error counts with severity normalization.

### C. Coherence modeling (important)

Use sentence-level coherence signals, not just grammar:

- paragraph organization pattern
- transition adequacy
- local sentence continuity

This matters because research shows high grammar does not guarantee coherence.

### D. Calibration layer

Even strong NLP models need calibration to rubric scales.

- Train isotonic/Platt or ordinal calibration per trait.
- Match model output bands to rubric categories.

### E. Review flags

Flag for human review when:

- low confidence
- disagreement between major scorers
- suspected memorized/template pattern
- unusual language pattern out of training distribution

## 6) Write Email implementation blueprint (PTE Core)

Write Email should be scored as a `rubric-gated analytic task`, not as generic essay scoring.

### A. Form + content gate (must run first)

Implement score-guide logic exactly:

1. Compute `Formal requirements` from word count + structure:
   - detect salutation
   - detect purpose statement
   - detect closing/sign-off
2. Compute `Content` validity:
   - on-topic with prompt purpose
   - intelligible and logically developed
   - not mere copied prompt text
3. Enforce gate rule:
   - if `Content = 0` or `Formal requirements = 0`, set Grammar/Vocabulary/Spelling to `0` and skip those model calls.
   - still emit all remaining rubric traits (including Email conventions) so output stays rubric-complete.

This gate rule is explicit in Pearson's Write Email criteria and should be implemented as deterministic business logic.

### B. Content scorer (0-3)

Model expected score behavior:

- `3`: complete response, clear purpose, strong audience fit, coherent development
- `2`: generally relevant but partially developed or with minor omission
- `1`: limited development or significant missing details
- `0`: off-topic, copied, not intelligible, or below minimum valid length

Practical features:

- prompt-intent extraction (what must be communicated)
- semantic coverage against required intents/details
- contradiction/off-topic penalty
- specificity bonus for prompt-grounded details

### C. Email conventions scorer (0-2)

This is the Write Email trait most often missed by generic AES systems.

Recommended features:

- register classifier (`formal`, `semi-formal`, `informal`)
- audience-role consistency (manager/teacher/service desk/friend)
- format consistency (subject-like opener, salutation, polite request framing, closing)
- pragmatic adequacy (clear request/action and professional tone when needed)

Score mapping:

- `2`: consistently appropriate format/register for purpose + audience
- `1`: mostly appropriate with noticeable mismatch
- `0`: poor or missing email conventions/register

### D. Grammar, vocabulary, spelling (0-2 each)

Implement as independent trait scorers:

- `Grammar`: error density + severity + sentence well-formedness
- `Vocabulary`: lexical range + precision + appropriateness to context
- `Spelling`: misspelling count normalized by length and severity

Do not collapse these into one "language quality" score before calibration.

### E. Anti-template and review flags

Add Write Email-specific risk controls:

- template similarity check (near-duplicate memorized email bodies)
- low prompt-entity anchoring (generic text that could fit any prompt)
- abnormal style distribution (forced complexity, irrelevant formal phrases)
- low confidence / scorer disagreement

### F. Feedback output examples

Return short, actionable feedback:

- "Purpose is clear, but closing/sign-off is missing."
- "Tone is too informal for the target recipient."
- "Main request is present, but key detail from prompt is missing."
- "Word count is outside full-score range for formal requirements."

## 7) How others implement similar scoring systems

### Pearson PTE Core (official score-guide behavior)

- Uses automated writing-scoring components (IEA/KAT with textual characteristics) trained against expert-scored responses.
- Uses trait-based scoring with explicit rule gates in Write Email criteria.
- This is a strong signal that production scoring should be `rubric-first`, then model-assisted.

### ETS e-rater (official product + research)

- Uses feature families including grammar/mechanics, style, lexical complexity, and organization/development.
- Uses statistical combination of features rather than one raw end-to-end score.
- Acts as a reliable reference for operational AES architecture.

### IELTS writing (official public process)

- Writing is assessed by trained human examiners using analytic criteria:
  - Task Achievement/Response
  - Coherence and Cohesion
  - Lexical Resource
  - Grammatical Range and Accuracy
- Official IELTS quality process emphasizes examiner training, regular monitoring, and remark channels.

### CELPIP writing (official public process)

- Speaking/writing are scored by trained raters independently.
- If two raters differ beyond threshold, a third rating is used.
- This is a reference design for human-adjudication loops around productive language tasks.

[Inference] Across providers, the stable production pattern is:
`explicit rubric criteria + trait-level scoring + calibration + quality controls`.

## 8) Research-backed model/metric choices

For SWT summarization quality:

- ROUGE as lexical baseline.
- BERTScore and BLEURT for stronger semantic alignment with human judgments.

For essay/email trait scoring:

- Neural AES models are strong baselines.
- Coherence-aware models reduce false high scores on superficially fluent but weakly organized responses.
- Sentence-level embeddings (SBERT) are practical for prompt relevance and coverage.
- For email register/convention signals, include formality and politeness modeling features.

Recommended evaluation split:

- `offline development metrics` for model iteration.
- `rubric-trait outputs` for product scoring and user-facing feedback.

## 9) Data, evaluation, and reliability plan

### Data

- Build prompt-wise dataset with double human scoring and adjudication.
- Store trait-level labels (not only total score).
- For Write Email, include varied audience/purpose distributions:
  - request
  - complaint
  - apology
  - information update

### Metrics

- Quadratic Weighted Kappa (overall + per trait).
- Trait-wise exact/adjacent agreement.
- Correlation with human scores.
- Calibration error by trait band.
- Gate accuracy:
  - precision/recall for `Form=0` and `Content=0` triggers.

### Reliability controls

- Prompt-stratified validation (avoid leakage).
- Drift monitoring by prompt/domain and response length.
- Fairness slices by L1/background where possible.
- Periodic re-benchmark against fresh human-scored samples.
- Human-review queue for low-confidence and anomaly flags.

## 10) Delivery roadmap (practical)

### Phase 1: Rubric-true baseline

- Implement hard gates and deterministic scoring skeleton for SWT/Essay/Write Email.
- Deliver transparent trait explanations.

### Phase 2: Model-assisted trait scoring

- Add semantic coverage + faithfulness model for SWT.
- Add essay trait models (content/coherence/language).
- Add Write Email conventions/register model.

### Phase 3: Calibration + QA

- Fit per-trait calibration to rubric bands.
- Add confidence, disagreement, and template-risk flags.

### Phase 4: Production hardening

- Monitoring dashboards and drift alerts.
- Prompt-family performance tracking.
- Scheduled human audit loop and rubric-version migration playbook.

## 11) Source-backed quote (for your presentation ending)

> "The contents of this Guide and the PTE Core website together provide the only official information about PTE Core."

Use this line to justify strict rubric-version control and why scoring logic must track official guide revisions.

## 12) Sources (with reliability notes)

1. Pearson PTE Academic Test Taker Score Guide (official)  
   Link: `https://www.pearsonpte.com/content/dam/pearson-pte/pte-academic/PTE-Academic-Test-Taker-Score-Guide.pdf`  
   Why reliable: Official Pearson scoring rubric/trait definitions for PTE Academic writing tasks.

2. Pearson PTE Core Score Guide (official)  
   Link: `https://www.pearsonpte.com/content/dam/pearson-pte/pte-core/PTE_Core_Score_Guide.pdf`  
   Why reliable: Official Pearson source for Write Email rubric, scoring logic, and automated scoring description.

3. Pearson PTE Core Teacher Guide (official)  
   Link: `https://www.pearsonpte.com/content/dam/pearson-pte/pdfs/guidebooks/PTE%20Core%20Teacher%20Guide.pdf`  
   Why reliable: Official product-positioning and task-structure reference (including Write Email replacing Essay in PTE Core).

4. ETS e-rater official overview  
   Link: `https://www.ets.org/erater.html`  
   Why reliable: Official ETS product documentation for automated essay scoring features.

5. ETS e-rater "How It Works"  
   Link: `https://www.ets.org/erater/how.html`  
   Why reliable: Official ETS description of scoring workflow and feature-based modeling.

6. ETS research report on e-rater microfeatures (RR-17-04)  
   Link: `https://www.ets.org/research/policy_research_reports/publications/report/2017/jxhq.html`  
   Why reliable: Official ETS research publication describing feature engineering and validity.

7. IELTS Writing assessment criteria (British Council official IELTS partner page)  
   Link: `https://takeielts.britishcouncil.org/take-ielts/prepare/free-ielts-english-practice-tests/ielts-writing-assessment-criteria`  
   Why reliable: Official IELTS partner guidance documenting analytic writing criteria.

8. IELTS reliability and quality-control process (official IELTS site)  
   Link: `https://ielts.org/researchers/our-research/how-we-ensure-ielts-tests-remain-secure-fair-and-reliable`  
   Why reliable: Official policy/process description for examiner quality control and score checks.

9. CELPIP performance standards and rating process (official)  
   Link: `https://www.celpip.ca/our-research/performance-standards/`  
   Why reliable: Official CELPIP process description for trained raters and adjudication behavior.

10. ROUGE (Lin, 2004)  
    Link: `https://aclanthology.org/W04-1013/`  
    Why reliable: Foundational ACL paper for summarization evaluation.

11. BERTScore (Zhang et al., 2019)  
    Link: `https://arxiv.org/abs/1904.09675`  
    Why reliable: Widely used semantic metric with stronger meaning-level correlation than n-gram overlap alone.

12. BLEURT (Sellam et al., ACL 2020)  
    Link: `https://aclanthology.org/2020.acl-main.704/`  
    Why reliable: ACL paper showing improved human-correlation behavior for generated text evaluation.

13. A Neural Approach to Automated Essay Scoring (Taghipour & Ng, EMNLP 2016)  
    Link: `https://aclanthology.org/D16-1193/`  
    Why reliable: Core neural AES benchmark paper.

14. Neural AES + coherence modeling (Farag et al., NAACL 2018)  
    Link: `https://aclanthology.org/N18-1024/`  
    Why reliable: Shows coherence signals are critical and shallow fluency can be misleading.

15. Sentence-BERT (Reimers & Gurevych, EMNLP 2019)  
    Link: `https://aclanthology.org/D19-1410/`  
    Why reliable: Standard sentence-embedding approach for semantic similarity and relevance checks.

16. Dear Sir or Madam, May I Introduce the GYAFC Dataset (Rao & Tetreault, NAACL 2018)  
    Link: `https://aclanthology.org/N18-1012/`  
    Why reliable: Standard benchmark dataset for modeling formality/register transformation.

17. A Computational Approach to Politeness (Danescu-Niculescu-Mizil et al., ACL 2013)  
    Link: `https://aclanthology.org/P13-1025/`  
    Why reliable: Foundational politeness modeling paper useful for audience/tone features in email scoring.
