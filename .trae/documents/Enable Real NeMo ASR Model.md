I have analyzed the ASR configuration and found that the **real ASR model is not running**.

### Status Analysis
The system is currently using a **mock implementation** instead of the actual NVIDIA NeMo model.
- **Active File**: `pte_core/asr/voice2text.py`
- **Behavior**: It imports from `pseudo_voice2text` and returns hardcoded timestamps/text regardless of the input audio file.
- **Reason**: The real model loading code is not present in the active file, likely to speed up development or avoid large model downloads during initial testing.

### Proposed Plan
Since you likely want to test with real audio, I propose we implement the actual ASR integration.

**Option 1: Enable Real NeMo ASR (Recommended)**
1.  **Modify `voice2text.py`** to load the real `nvidia/parakeet-ctc-0.6b` model using `nemo_toolkit`.
2.  Implement the actual transcription and timestamp extraction logic.
3.  Run a test to verify it transcribes your specific audio file correctly.

**Option 2: Continue with Mock (Debugging Only)**
- If you are only testing the *scoring logic* and don't care about the actual audio transcription, we can leave it as is.

**Shall I proceed with Option 1 to enable the real ASR model?**