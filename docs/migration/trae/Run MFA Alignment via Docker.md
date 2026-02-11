# Run MFA Alignments and ASR Parakeet Transcription

This plan covers the targeted MFA alignments (Indian and US ARPA) and the implementation/execution of the ASR Parakeet model within Docker.

## Phase 1: MFA Alignments (Docker)
We will run the forced alignment for the Indian and US ARPA accents as requested.
- **Indian Accent**: Outputs to `output_indian/`.
- **US ARPA Accent**: Outputs to `output_us/`.

```powershell
# Indian Accent
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/eng_indian_model/english_india_mfa.dict /data/eng_indian_model/english_mfa.zip /data/output_indian --clean

# US ARPA Accent
docker run -it --rm -v C:/Users/Acer/DataScience/PTE/PTE_MFA_TESTER_DOCKER:/data mmcauliffe/montreal-forced-aligner:latest mfa align /data/data /data/eng_us_model/english_us_arpa.dict /data/eng_us_model/english_us_arpa.zip /data/output_us --clean
```

## Phase 2: ASR Parakeet Implementation
Since the current Docker service only supports grammar, we will update it to include the **NVIDIA Parakeet** ASR model.

1. **Update `PTE_ASR_GRAMMAR_DOCKER`**:
   - **`requirements.txt`**: Add `nemo_toolkit[asr]`, `omegaconf`, and `torch`.
   - **`Dockerfile`**: Install system dependencies required by NeMo (`libsndfile1`, `ffmpeg`).
   - **`app.py`**: 
     - Initialize the `nvidia/parakeet-tdt-1.1b` model.
     - Add a `/asr` POST endpoint to handle audio file uploads and return transcribed text.

2. **Build & Start ASR Service**:
   - Run the updated `build_and_run_docker.ps1` to rebuild the image and start the container on port 8000.

## Phase 3: Transcribe Audio
Once the service is live, we will:
- Send `PTE_MFA_TESTER_DOCKER/data/Cs_degree.wav` to the `/asr` endpoint.
- Retrieve and display the transcribed text.

**Please confirm if you are ready to proceed with these steps.**
