I will implement the "Describe Image" evaluation pipeline, integrating ASR (Whisper), Grammar Check (LanguageTool), MFA-based Fluency/Pronunciation scoring, and LLM-based Content evaluation.

1.  **Dependencies**:
    *   Add `openai-whisper` and `language-tool-python` to `requirements.txt`.

2.  **Create `describe_image` Module**:
    *   Create directory `describe_image/`.
    *   Create `describe_image/__init__.py`.

3.  **ASR Implementation (`describe_image/asr.py`)**:
    *   Implement `transcribe_audio(wav_path, model="medium")` using `whisper`.
    *   This will return the transcript and word timestamps (if available/needed).

4.  **Grammar Check (`describe_image/grammar.py`)**:
    *   Implement `check_grammar(text)` using `language_tool_python.LanguageTool('en-US')`.
    *   Return a list of grammar issues to be included in the LLM prompt.

5.  **Fluency & Pronunciation (`describe_image/fluency.py`)**:
    *   Implement `analyze_fluency_and_pronunciation(wav_path, transcript)`.
    *   Use `pte_core.mfa.pronunciation.assess_pronunciation_mfa` with the transcript as the reference text.
    *   Extract:
        *   **Pronunciation Score**: From MFA's acoustic/phone quality scores (`score_pte`).
        *   **Fluency Score**: Calculate based on speech rate and pause duration (using metrics from MFA).
    *   Return a dictionary with these scores.

6.  **Prompt Template (`describe_image/prompts.py`)**:
    *   Store the user's prompt template string.

7.  **Evaluator (`describe_image/evaluator.py`)**:
    *   Implement `DescribeImageEvaluator` class.
    *   Method `evaluate_image_description(wav_path, image_schema)`:
        1.  Run ASR -> Transcript.
        2.  Run Grammar Check -> Issues.
        3.  Run MFA -> Fluency/Pronunciation Scores.
        4.  Construct Prompt (using transcript, scores, issues, image schema).
        5.  Call LLM (Placeholder/Mock).
    *   Return the final JSON response.

8.  **Documentation & Testing**:
    *   Create `describe_image/README.md`.
    *   Create `describe_image/test_pipeline.py` to demonstrate the flow.

This approach leverages existing MFA infrastructure while adding the requested new components (Whisper, LanguageTool).