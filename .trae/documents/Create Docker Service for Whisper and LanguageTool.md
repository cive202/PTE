I will create a separate Docker service for ASR (Whisper) and Grammar Checking (LanguageTool) and update the client code to use it.

1.  **Create Docker Service Directory**: `PTE_ASR_GRAMMAR_DOCKER/`

2.  **Create `app.py`**:
    *   A **FastAPI** application exposing two endpoints:
        *   `POST /asr`: Accepts an audio file, runs Whisper, returns text.
        *   `POST /grammar`: Accepts text, runs LanguageTool, returns issues.

3.  **Create `Dockerfile`**:
    *   Base image: `python:3.10-slim`.
    *   System dependencies: `ffmpeg` (for Whisper), `openjdk-17-jre-headless` (for LanguageTool).
    *   Python dependencies: `openai-whisper`, `language-tool-python`, `fastapi`, `uvicorn`, `python-multipart`.
    *   Command: Run `uvicorn app:app --host 0.0.0.0 --port 8000`.

4.  **Create `docker-compose.yml`** (optional, but helpful for running it):
    *   Define the service mapping port 8000:8000.

5.  **Update Client Code in `describe_image/`**:
    *   `asr.py`: Switch from local import to HTTP POST request to `http://localhost:8000/asr`.
    *   `grammar.py`: Switch from local import to HTTP POST request to `http://localhost:8000/grammar`.

6.  **Update Project Dependencies**:
    *   Remove `openai-whisper` and `language-tool-python` from the main `requirements.txt`.
    *   Ensure `requests` is in `requirements.txt`.

7.  **Verification**:
    *   The user will need to build and run the Docker container. I will provide the commands to do so.
    *   The existing `test_pipeline.py` will serve as the verification script once the container is running.

I will start by setting up the Docker files.