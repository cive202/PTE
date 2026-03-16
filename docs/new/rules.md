# PTE App Rules And Scoring

This file is the compact source of truth for the current app behavior.

Scope:
- Speaking
- Reading
- Writing

Excluded on purpose:
- Listening objective tasks except where they share important writing-like rules

Important:
- Some rules below are exact product rules from this repo.
- Some speaking pause and fluency timings are product heuristics, not official Pearson millisecond rules.
- Rich pause and gap timing is best when MFA is enabled. Without MFA, the system falls back to weaker ASR timing.

## 1. Shared Speaking Rules

### 1.1 Core speaking pipeline
- Audio is transcribed with ASR.
- Reference text and transcript are aligned word by word.
- If MFA is available, word and phone timings are added.
- Matched words get phoneme analysis, stress analysis, and combined pronunciation scoring.
- Punctuation boundaries get pause evaluation.
- Extra long non-punctuation silences become blue gap markers in the UI.

### 1.2 Word status meanings
- `correct`: word matched the reference text and survived pronunciation scoring.
- `mispronounced`: word matched textually, but pronunciation/stress score dropped too low.
- `inserted`: extra spoken word not in the reference.
- `omitted`: reference word missing in the spoken response.
- `correct_pause`: punctuation pause is inside ideal range.
- `short_pause`: punctuation pause exists but is shorter than ideal.
- `long_pause`: punctuation pause exists but is longer than ideal.
- `missed_pause`: expected punctuation pause is missing.
- `extra_gap`: non-punctuation gap is longer than the ideal word-to-word limit.

### 1.3 Phoneme scoring
- Exact phoneme match: `1.00`
- Accent-accepted substitution: `0.70`
- Similar but non-exact phones: `0.65 / 0.50 / 0.35 / 0.20 / 0.05` depending on feature distance.
- Missing or extra aligned phoneme slot: `0.00`
- Length mismatch penalty: `8` points per missing or extra phoneme.
- If accent substitutions are used, the word takes an additional `15` point penalty.

### 1.4 Stress scoring
- Perfect stress match: `1.0`
- Acceptable secondary-stress variation: `0.9`
- Syllable-count mismatch: `0.8`
- Stress mismatch: `0.5`
- No vowels detected: `0.0`

Stress warning logic:
- Stress is flagged when score `< 0.85`, or match info indicates mismatch.
- Stress is not flagged for `perfect match` or `acceptable variation`.

### 1.5 Final word pronunciation decision
- Combined word score:

```text
combined = 0.7 * phoneme_accuracy + 0.3 * (stress_score * 100)
```

- If combined score `< 55%`, the word becomes `mispronounced`.
- This means phonemes are the main driver and stress is a secondary driver.

### 1.6 Single-word practice thresholds
- `correct`: accuracy `>= 75`
- `acceptable`: accuracy `>= 55` and `< 75`
- `mispronounced`: accuracy `< 55`

### 1.7 Pause timing rules

These are current product heuristics.

| Boundary | Ideal range |
| --- | --- |
| Comma `,` | `0.25s - 0.50s` |
| Semicolon `;` | `0.35s - 0.65s` |
| Colon `:` | `0.35s - 0.65s` |
| Full stop `.` | `0.60s - 1.00s` |
| Exclamation `!` | `0.60s - 1.00s` |
| Question `?` | `0.60s - 1.00s` |
| Normal word-to-word gap | `0.08s - 0.25s` |

Pause penalties:
- Missed comma: light penalty `0.05`
- Missed semicolon/colon: `0.18`
- Missed sentence-final punctuation: `0.30`
- Very long pause above `1.5s`: full penalty
- Small short-pause misses inside a `30%` soft floor are ignored
- Pauses after function words are softened
- Pause after repeated words is amplified

### 1.8 Hesitation clustering
- Multiple pauses close together are treated more harshly than isolated pauses.
- Cluster window: `2.0s`
- Each extra pause in the cluster adds `20%` penalty amplification.

### 1.9 Pause and gap UI colors
- Green: ideal punctuation pause
- Yellow: punctuation pause too short or too long
- Red: missed punctuation pause
- Blue: extra non-punctuation gap beyond ideal word-gap range

### 1.10 Speaking summary fields
- `correct`
- `mispronounced`
- `inserted`
- `omitted`
- `stress_issues`
- `pause_penalty`
- `pause_count`
- `speech_rate_scale`

## 2. Speaking Tasks

### 2.1 Read Aloud

Current scoring style:
- No calibrated overall `0-90` score yet.
- Main result is word-level analysis plus summary counts.

What it evaluates:
- Text alignment accuracy
- Word pronunciation
- Stress
- Punctuation pauses
- Extra long within-sentence gaps

Main summary:
- Accuracy-style view is based on matched `correct` words vs total words.
- Pause penalties are shown separately.

Best use:
- Deep pronunciation and pause practice, not final exam-equivalent score.

### 2.2 Repeat Sentence

Current scoring style:
- Same shared speech pipeline as Read Aloud.
- No calibrated overall `0-90` score yet.

What it evaluates:
- Word-by-word alignment against the target sentence
- Pronunciation and stress on matched words
- Insertions and omissions
- Pause timing and extra gaps

Best use:
- Recall + pronunciation practice
- Strong for seeing what was omitted, inserted, or mispronounced

### 2.3 Describe Image

Output score:
- Total `0-90`

Subscores:
- Content `0-90`
- Pronunciation `0-90`
- Fluency `0-90`

Internal weighting:
- Content: `36` raw points
- Pronunciation: `27` raw points
- Fluency: `27` raw points
- Final total is capped at `90`

#### Content gate
If content is effectively unusable, total score becomes `0` and pronunciation/fluency do not contribute.

Content gate triggers when:
- response is too short
- semantic match is very weak and keyword coverage is very weak
- response looks template-heavy and still has weak image relevance

#### Content score
- Semantic similarity: max `22` points
- Keyword coverage: max `10` points
- Number coverage: max `4` points

#### Pronunciation score
- Uses MFA word-level `accuracy_score` when available
- Inserted words count as `0`
- Correct words without explicit accuracy may count as full credit
- Mispronounced words count as `0`
- Omitted words are not double-penalized in this pronunciation average

#### Fluency score
- Structure: max `9`
  - intro pattern present: `+3`
  - conclusion pattern present: `+3`
  - trend language present: `+3`
- Length fit: max `9`
  - best if response length is `0.6x - 1.5x` the reference length
- Time fit: max `9`
  - best if response duration is inside the configured target range

Structure signals:
- Intro: phrases like `the chart shows`, `this graph illustrates`
- Conclusion: `overall`, `in conclusion`, `to summarize`
- Trends: `increase`, `decrease`, `highest`, `lowest`, `peak`, `stable`, etc.

### 2.4 Retell Lecture

Output score:
- Total `0-90`

Subscores:
- Content `0-90`
- Pronunciation `0-90`
- Fluency `0-90`

Internal weighting:
- Content: `42` raw points
- Pronunciation: `24` raw points
- Fluency: `24` raw points
- Final total is capped at `90`

#### Content gate
If content quality is too low, total score becomes `0`.

Content gate triggers when:
- response is too short
- semantic similarity, keyword coverage, and key-point coverage are all weak
- response looks template-heavy and still has weak lecture relevance

#### Content score
- Semantic similarity: max `22`
- Keyword coverage: max `8`
- Key-point coverage: max `12`

Key-point coverage:
- A key point is treated as covered if semantic similarity to that point is at least `0.38`

#### Pronunciation score
- Same MFA-derived pronunciation aggregation approach as Describe Image

#### Fluency score
- Structure points:
  - lecture context words present: `+2.5`
  - at least 2 connectors: `+2.5`
  - 1 connector: `+1.2`
  - summary phrase present: `+3.0`
- Duration fit: max `8`
- Pace fit: max `8`
- Filler penalty:
  - filler ratio `> 0.06`: `-2`
  - filler ratio `> 0.03`: `-1`

Structure signals:
- Context terms such as `lecture`, `talk`, `speaker`, `presentation`
- Connector count from linking words
- Summary phrases such as `overall`, `in summary`, `in conclusion`

### 2.5 Summarize Group Discussion
- UI exists
- Marked as soon available
- No implemented scoring engine yet

### 2.6 Respond To A Situation
- UI exists
- Marked as soon available
- No implemented scoring engine yet

## 3. Reading Tasks

Reading tasks in this repo are deterministic and mostly objective.

### 3.1 Multiple Choice, Multiple Answers
- Score rule: `+1` for each correct selected option
- Penalty: `-1` for each incorrect selected option
- Floor: minimum total `0`
- Max score: number of correct options

### 3.2 Multiple Choice, Single Answer
- Correct answer: `1`
- Incorrect or unanswered: `0`

### 3.3 Fill In The Blanks (Dropdown)
- `1` point per correct blank
- No negative marking
- Max score: number of blanks

## 4. Writing Shared Rules

### 4.1 Grammar source
- Primary source: grammar service
- Fallback if service is unavailable:
  - missing capital at start
  - missing sentence-ending punctuation
  - repeated whitespace
  - excessive punctuation like `...` or `!!!`

### 4.2 Shared grammar score

Grammar score is error-rate based:
- `2`: grammar error rate `<= 4.0%`
- `1`: grammar error rate `<= 9.0%`
- `0`: above that

### 4.3 Shared spelling score
- `2`: spelling error rate `<= 1.5%`
- `1`: spelling error rate `<= 3.5%`
- `0`: above that

### 4.4 Shared vocabulary score

Signals:
- type-token ratio
- average word length

General rule:
- `2`: strong lexical variety and average word length
- `1`: moderate lexical variety
- `0`: weak variety / repetitive vocabulary

For longer writing:
- top tier usually needs type-token ratio about `>= 0.50`

## 5. Writing Tasks

### 5.1 Summarize Written Text

Output:
- Total `0-7`

Trait weights:
- Content: `0-2`
- Form: `0-1`
- Grammar: `0-2`
- Vocabulary: `0-2`

#### Form rules
- Word count must be `5-75`
- Must be exactly one sentence
- Must end with terminal punctuation

If form fails:
- total score becomes `0`

#### Content score
Based on keyword coverage from the source passage:
- `2`: coverage `>= 66%`
- `1`: coverage `>= 40%`
- `0`: below that

#### Vocabulary adjustment
- If copied-token ratio `> 78%` and response has at least `15` words, vocabulary score loses `1`

### 5.2 Write Essay

Output:
- Total `0-20`

Trait weights:
- Content: `0-6`
- Form: `0-2`
- Development, structure, coherence: `0-6`
- Grammar: `0-2`
- Vocabulary: `0-2`
- Spelling: `0-2`

#### Form score
- `2`: `200-300` words
- `1`: `120-380` words
- `0`: outside that

#### Content score
Based on prompt-keyword coverage:
- `6`: `>= 70%`
- `5`: `>= 55%`
- `4`: `>= 42%`
- `3`: `>= 30%`
- `2`: `>= 20%`
- `1`: `>= 12%`
- `0`: below that

#### Development, structure, coherence
- Paragraph points:
  - `2` if `2-5` paragraphs
  - `1` if at least `1`
- Sentence points:
  - `2` if at least `8` sentences
  - `1` if at least `5`
- Transition points:
  - `2` if at least `4` transition hits
  - `1` if at least `2`

#### Off-topic cap
- If prompt relevance is `< 10%` and word count is at least `120`, total score is capped at `6`

### 5.3 Write Email

Output:
- Total `0-13`

Trait weights:
- Content: `0-3`
- Formal requirements: `0-2`
- Grammar: `0-2`
- Vocabulary: `0-2`
- Spelling: `0-2`
- Email conventions: `0-2`

#### Formal requirements
Structure signals:
- salutation
- purpose statement
- closing

Score:
- `2`: `50-120` words and all 3 structure elements present
- `1`: `30-150` words and at least 2 structure elements present
- `0`: otherwise

#### Content score
- `0` if under `30` words
- `3`: keyword relevance `>= 52%`
- `2`: `>= 32%`
- `1`: `>= 18%`
- `0`: below that

#### Email conventions
Signals:
- polite markers such as `please`, `could you`, `would you`, `kindly`, `thank you`
- informal markers such as `gonna`, `wanna`, `btw`, `thx`, `pls`

Score:
- `2`: strong structure, at least one polite marker, no informal markers
- `1`: at least two structure elements and not too informal
- `0`: otherwise

#### Gate
If either of these is `0`:
- content score
- formal requirements score

Then:
- grammar score becomes `0`
- vocabulary score becomes `0`
- spelling score becomes `0`

This is an explicit cap gate for weak task completion.

## 6. Quick Reference Tables

### 6.1 Speaking pause and gap ranges

| Type | Range |
| --- | --- |
| Comma | `0.25s - 0.50s` |
| Semicolon | `0.35s - 0.65s` |
| Colon | `0.35s - 0.65s` |
| Full stop | `0.60s - 1.00s` |
| Exclamation | `0.60s - 1.00s` |
| Question | `0.60s - 1.00s` |
| Normal word gap | `0.08s - 0.25s` |

### 6.2 Speaking word thresholds

| Rule | Threshold |
| --- | --- |
| Stress warning | `< 0.85` |
| Word becomes `mispronounced` | combined `< 55%` |
| Word practice `correct` | `>= 75%` |
| Word practice `acceptable` | `55% - 74.9%` |
| Word practice `mispronounced` | `< 55%` |

### 6.3 Writing form windows

| Task | Best range | Allowed outer range |
| --- | --- | --- |
| Summarize Written Text | one sentence, `5-75` words | same |
| Write Essay | `200-300` words | `120-380` words |
| Write Email | `50-120` words | `30-150` words |

## 7. Current Limitations

- Read Aloud and Repeat Sentence do not yet have a calibrated final `0-90` speaking score.
- Pause and gap timing is strongest only when MFA timings are available.
- Speaking pause thresholds are repo heuristics, not published Pearson official pause targets.
- Summarize Group Discussion and Respond To A Situation are present as pages but are not yet scored.

## 8. Source Files

- `pte_core/pause/rules.py`
- `pte_core/pause/pause_evaluator.py`
- `pte_core/pause/hesitation.py`
- `pte_core/pause/speech_rate.py`
- `api/validator.py`
- `api/image_evaluator.py`
- `api/lecture_evaluator.py`
- `api/writing_evaluator.py`
- `api/reading_evaluator.py`
