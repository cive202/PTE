# Read Aloud

## Feature (Short)
User reads on-screen text aloud; system evaluates spoken delivery against the displayed passage.

## Real PTE (Public)
- In PTE Academic Part 1, prompt text is up to 60 words.
- Public guidance indicates machine scoring for speaking traits; exact model internals are not published.

## Our Implementation
- Page: `api/templates/index.html`
- Prompt APIs: `/speaking/read-aloud/get-topics`, `/speaking/read-aloud/get-passage`
- Submission/scoring: `/check_stream` with `feature=read_aloud`
- Engine: `api/validator.py` (`align_and_validate_gen`)
- Data: `data/reference/read_aloud/references.json`

## Simple Architecture
UI text selection -> record audio -> `/check_stream` -> ASR + MFA + pause analysis -> word-level result JSON

## Reliability
- Good for granular pronunciation/fluency feedback.
- Current UI score is accuracy-style summary (`correct/total`), not a calibrated exam-equivalent 0-90 scale.

## Remaining Improvements
- Add stable scaled scoring layer (content/pronunciation/fluency -> 0-90).
- Add benchmark set with expert-rated samples.
- Add stricter handling of reading hesitations and self-corrections.

## Simple Conclusion: What Is Actually Used Now
- Audio -> WAV conversion uses `ffmpeg` in the Flask API before scoring starts.
- Audio -> text uses Parakeet ASR (`nvidia/parakeet-ctc-0.6b`) from the `asr-grammar` service.
- Text/content check uses the ASR transcript compared with the reference passage in `api/validator.py`.
- Word and phone timing uses MFA (Montreal Forced Aligner) through Docker. This is the main pronunciation alignment layer.
- Yes, `wav2vec2` is also used, but not as the main full-passage aligner. It is used by the phoneme microservice for word-level phoneme fallback when MFA phone evidence is missing or for fast single-word practice.
- Stress analysis uses the aligned word segment plus expected stress from CMUdict / `g2p_en`.
- Pause and fluency analysis use punctuation-aware pause scoring from the aligned timings.
- Grammar checking is available in the shared `asr-grammar` service, but it is not the main Read Aloud scoring component.

In short: `audio -> ffmpeg -> Parakeet ASR -> MFA alignment -> phoneme/stress/pause analysis -> word-level feedback`. `wav2vec2` is used as a supporting phoneme checker, not the primary Read Aloud transcription engine.

## Recommendation
- Do not replace Parakeet with a wav2vec2 phoneme model. Parakeet is serving the transcript ASR role.
- Do not replace MFA with a wav2vec2 phoneme model. MFA is serving the known-text alignment and timing role.
- If the phoneme stack is improved later, the change should target only the fallback phoneme microservice, not the whole Read Aloud pipeline.

## References
- https://www.pearsonpte.com/pte-academic/test-format/speaking-writing
- https://www.pearsonpte.com/content/dam/brand-folder/global/pearson-dot-com/files/pte/PTE_Academic_Test_Taker_Score_Guide_2025_03.pdf
