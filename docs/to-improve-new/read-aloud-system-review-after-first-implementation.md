# Read Aloud System Review After Full Implementation Wave

Last reviewed: March 30, 2026

## 1. Scope

This review judges the system after the recent implementation wave that now includes:

- Task 01: regression fixtures and test harness
- Task 02: content alignment and normalization cleanup
- Task 03: boundary realization and pause separation
- Task 04: pronunciation variant handling
- Task 05: stress reliability handling
- Task 06: explicit score contract and UI rollout
- Task 07: benchmark and calibration scaffold
- expected-word realization rewrite to reduce transcript-led correctness

This document replaces the earlier first-wave review. It is meant to describe the current code state, not the earlier transitional state.

## 2. Short answer

The system is now substantially closer to the correct Read Aloud architecture.

It is no longer fair to call it mainly transcript-led in the same way as before.
It is now a hybrid known-text pronunciation system with:

- reference-conditioned word targets
- MFA timing and word segmentation
- phoneme-service evidence for observed phones
- explicit pronunciation, completeness, stress, prosody, and fluency scores
- a UI contract where punctuation and gaps no longer reduce the main displayed accuracy

However, it is still not the ideal final system from the research.

Current overall judgment:

- `architecture direction`: strong
- `engineering structure`: strong
- `current scoring validity`: improved, but still partly heuristic
- `calibration maturity`: still weak

Updated overall grade:

- before the recent work: about `B- foundation / C scoring logic`
- after Tasks 01 to 05: about `B foundation / B- engineering direction / C+ scoring maturity`
- after Tasks 06 to 07 plus expected-word realization rewrite: about `A- foundation / B+ system design / B scoring maturity / C+ calibration maturity`

Interpretation:

- the system now solves several of the earlier architectural mistakes
- it now behaves much closer to a serious PTE-style practice scorer
- it still is not yet a fully calibrated assessment system

## 3. What the current system now does well

## 3.1 Overall accuracy is now separated from punctuation and random gaps

This is one of the most important fixes.

The system now exposes explicit scores for:

- overall accuracy
- pronunciation accuracy
- completeness
- stress
- prosody
- fluency

The main displayed accuracy is now pronunciation-focused rather than being reduced by comma timing, full-stop timing, or random inter-word gap issues.

Judgment:

- this directly solves one of the main product mistakes from before
- this is much closer to how the system should behave for learner trust

Result:

- punctuation and gap timing still matter
- but they now sit in `fluency` and `prosody`, not in the main accuracy display

## 3.2 Content scoring is no longer purely transcript-led

This was the biggest earlier architectural criticism.

What changed:

- the matcher now keeps expected reference words as the primary units
- substitutions no longer immediately become final lexical deletions
- expected words can survive long enough to be judged by acoustic evidence
- final word status is now resolved with `content_support` and `content_status`

Practical meaning:

- if ASR says a different word, the system does not blindly trust that transcript and immediately fail the expected word
- the system now asks a better question:
  - was the expected word realized clearly enough?

Judgment:

- this is a real architecture correction
- this is the biggest technical improvement in the current wave

Important limitation:

- the system still uses transcript alignment as the initial lexical scaffold
- it is not yet a true constrained decoder or direct expected-word detector

So this gap is reduced a lot, but not eliminated completely.

## 3.3 The punctuation model is much more defensible than before

What changed:

- punctuation remains preserved from the reference
- pause timing uses explicit expected ranges
- `boundary_realization` softens no-silence or low-silence cases
- `weak_pause_but_good_boundary` captures cases where the speaker marked a boundary without a strong silent pause

This is especially relevant to the earlier concern about long `s` or `sh` sounds before punctuation.

Current judgment:

- the system now handles those cases far better than before
- such events no longer automatically behave like plain missed pauses
- they also do not reduce the main displayed pronunciation accuracy

This is the correct direction.

## 3.4 Phoneme matching is now fairer

What changed:

- multiple valid expected pronunciations are supported
- the scorer can choose the best matching expected variant

This fixes a major fairness issue from the earlier system:

- words no longer fail just because only one canonical pronunciation was accepted

Judgment:

- this is a strong practical improvement
- it is closer to how a real pronunciation tutor should behave

## 3.5 Stress is handled more honestly than before

What changed:

- `stress_reliable` now exists
- weak evidence no longer becomes a confident stress error
- single-syllable or ambiguous cases are treated more cautiously

Judgment:

- much better than the earlier version
- the system is less likely to pretend confidence where it does not have it

## 3.6 The product contract is now much clearer

This was missing before.

The system now has a much better contract between backend and UI:

- scores are explicit
- word-level feedback is more explainable
- modal details can show silent gap vs boundary quality
- the UI language now better matches the actual backend design

Judgment:

- this is important product engineering
- the backend and frontend are finally closer to the same mental model

## 3.7 There is now at least a calibration scaffold

What now exists:

- benchmark manifest
- benchmark rating specs
- benchmark evaluation script
- tests for the harness itself

Judgment:

- this does not mean calibration is done
- but it means the project finally has a place to put real evidence instead of only opinions

This is a meaningful improvement.

## 3.8 Runtime behavior is safer for stream responses

The API entrypoint no longer starts with Flask `debug=True` by default.

Why this matters:

- development reloader behavior is a bad default for long-running stream responses
- the Read Aloud UI depends on an NDJSON stream from `/check_stream`
- disabling debug and reloader by default reduces one likely source of transient browser-side stream failures

Judgment:

- this is a practical runtime hardening step
- it does not prove every stream error is solved
- but it removes an avoidable reliability risk from the main speaking flow

## 4. Does the current system accomplish the original concerns?

## 4.1 Concern: comma and full-stop gap detection around long `s` or `sh`

Current answer:

- `partly yes`

Why:

- the system now distinguishes punctuation timing from main pronunciation accuracy
- the system can now treat some no-silence boundaries as `weak_pause_but_good_boundary`
- so the long fricative case is no longer handled in the earlier naive way

But not fully:

- the current boundary model is still heuristic
- it still does not use a richer prosody stack such as:
  - explicit VAD-backed silence modeling
  - pitch reset detection
  - phrase-level F0 movement
  - reset of energy contour after the boundary

Judgment:

- this concern is now handled much better
- but the current system still uses an informed heuristic, not a mature prosody engine

## 4.2 Concern: is stress really included, and should it be this important?

Current answer:

- `yes, stress is included`
- `yes, it still matters, but less than before`

Current implementation:

- per-word combined pronunciation score still uses:
  - `90% phoneme accuracy`
  - `10% stress`

Judgment:

- this is a much safer temporary policy than the earlier `70/30`
- it matches the product goal that clear mispronunciation should dominate the main accuracy score
- it is still a local policy choice, not an official published Pearson number

Why:

- stress handling is safer now
- Pearson does not publish an exact internal stress percentage
- public pronunciation-assessment practice supports keeping prosody or stress meaningful without letting it dominate segmental accuracy

Recommendation:

- keep the current `90/10` split until calibration evidence says otherwise
- continue exposing separate `stress` and `prosody` scores so users can still see suprasegmental weakness directly

## 4.3 Concern: is phoneme matching too strict or too loose?

Current answer:

- it is much better than before
- but it is not fully solved

Why it is better:

- multiple pronunciation variants are accepted
- accent-tolerant matching exists
- the system no longer behaves like a single exact-pronunciation checker

Why it is still incomplete:

- phoneme scoring still relies on heuristic substitution rules and weights
- there is still no expert-rated calibration proving where the strictness should sit
- the current fallback path can still use MFA-aligned phone labels when the phoneme recognizer does not return usable phones

Judgment:

- fairness is clearly improved
- exact final strictness is still not evidence-backed yet

## 5. What is still below the ideal architecture

## 5.1 It is still not a true constrained known-text decoder

The current system is much closer to the right thing, but the ideal architecture would do even more:

- use the known prompt to constrain decoding more directly
- judge each expected word from acoustic realization, not mainly from transcript alignment plus post-resolution

Current system:

- better than transcript-led ASR diffing
- not yet a true expected-word recognizer

Judgment:

- strong improvement
- still not the final form

## 5.2 Observed-phone evidence is still not fully clean

Important remaining criticism:

- the system prefers phoneme-service output
- but it can still fall back to MFA-aligned phones if the phoneme-service output is missing

Why this matters:

- MFA phone labels are alignment labels tied to the reference path
- they are useful operationally
- but they are not as strong as an independent observed-phone measurement

Risk:

- fallback behavior can still over-credit some words

Judgment:

- acceptable as a fallback
- not ideal as long-term scoring evidence

## 5.3 Boundary scoring is still heuristic, not fully prosodic

The current boundary model is good enough to avoid the earlier worst mistake.

But it is still limited because it does not model:

- pitch reset
- phrase-final melodic drop or continuation rise
- energy reset after punctuation
- richer silent-gap segmentation

Judgment:

- conceptually correct
- still only a first prosody layer

## 5.4 Stress is safer, but still overweighted relative to detector maturity

This is no longer the most important scoring criticism.

The earlier review said stress was unreliable.
That is less true now because reliability gating exists.
But the deeper point still remains:

- the detector is still heuristic
- even at `10%`, the final number is still a policy choice rather than an evidence-calibrated truth

Judgment:

- the problem has moved from "stress handling is badly designed"
- to "stress handling is conservatively weighted, but still not benchmark-calibrated"

## 5.5 Calibration is still only scaffolding

This must be said clearly:

- benchmark support now exists
- real calibration still does not

What is still missing:

- real audio benchmark sets
- expert or trusted reviewer labels
- before/after threshold studies
- evidence-backed tuning of weights

Judgment:

- strong structural progress
- real scoring validity still needs evidence

## 5.6 UI rollout is improved, but not totally universal

The main Read Aloud and Repeat Sentence paths now consume the clearer score contract.

That is good.

But the broader product still needs consistency if the same transcription overlay concepts are reused elsewhere.

Judgment:

- largely solved for the main path
- still worth auditing across the rest of the speaking product

## 6. Current scorecard by subsystem

## 6.1 Content and completeness

Current grade: `A-`

Why:

- normalization issues were fixed
- expected words now survive long enough to be judged properly
- the system is no longer just a transcript diff

Main remaining gap:

- not yet a true constrained expected-word recognizer

## 6.2 Pronunciation scoring

Current grade: `B+`

Why:

- valid pronunciation variants are supported
- observed-phone evidence is preferred
- word-level statuses are more defensible now

Main remaining gap:

- heuristic scoring and fallback dependence on alignment labels

## 6.3 Stress

Current grade: `B-`

Why:

- reliability handling is much better
- the detector is still not strong enough to justify total confidence
- the new `10%` weighting is much closer to a reasonable interim setting

## 6.4 Pause, punctuation, and phrasing

Current grade: `B`

Why:

- punctuation no longer damages the wrong score
- boundary realization heuristic is useful

Main remaining gap:

- still not a full prosody model

## 6.5 Product contract and explainability

Current grade: `A-`

Why:

- explicit scores now exist
- UI messaging is much clearer
- learner-facing interpretation is far better than before

## 6.6 Benchmarking and calibration

Current grade: `C+`

Why:

- scaffold exists
- actual evidence layer still does not

## 7. Final judgment

Compared with how the system should ideally work:

- the current system is now much closer
- it solves most of the original structural mistakes
- it does not yet solve the final validity problem

So the honest answer to:

- "does this new system accomplish the things?"

is:

- `yes, mostly for architecture`
- `yes, mostly for product behavior`
- `partly for scoring validity`
- `not yet for full calibration and final evidence-backed trust`

In plainer terms:

- the system now behaves like a serious pronunciation-practice engine
- it is no longer mainly a transcript toy with phoneme decoration
- but it is still not yet a fully calibrated assessment engine

## 8. Clear recommendations from here

## 8.1 Highest priority

Build a real benchmark set with actual audio and trusted labels.

Without that, the system still cannot prove that the current weights and thresholds are right.

## 8.2 Next scoring correction

Benchmark the current `10%` stress contribution against rated audio.

Recommendation:

- keep `90/10` unless benchmark evidence supports a change
- if benchmark evidence shows instability, reduce stress further or move more of that effect into separate prosody reporting

## 8.3 Next architecture improvement

Reduce dependence on transcript-seeded alignment even further.

Recommendation:

- move closer to a constrained known-text expected-word recognizer
- make omission and substitution logic less dependent on ASR lexical scaffolding

## 8.4 Next prosody improvement

Upgrade boundary scoring with richer signals:

- VAD-backed silence
- F0 reset or contour change
- energy reset after punctuation

## 8.5 Next pronunciation improvement

Treat MFA-phone fallback as lower-confidence evidence, not equal evidence.

That will make the system more honest when independent observed phones are unavailable.
