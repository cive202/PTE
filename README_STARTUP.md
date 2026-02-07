# How to Run the PTE Scoring Engine

This guide provides step-by-step instructions to set up and run the PTE Scoring Engine on your local machine.

## Prerequisites

1.  **Docker Desktop**:
    *   Must be installed and running.
    *   Required for background services and MFA alignment.
2.  **Python 3.10+**: Ensure Python is installed and added to your PATH.
3.  **FFmpeg**:
    *   Must be installed and accessible via command line (`ffmpeg -version`).
    *   **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your System PATH.
    *   **Mac/Linux**: Install via `brew install ffmpeg` or `sudo apt install ffmpeg`.

## Installation

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd PTE
    ```

2.  **Start Background Services (Docker)**:
    This starts the ASR/Grammar service (Port 8000) and the Phoneme service (Port 8001).
    ```bash
    docker-compose up -d --build
    ```
    *   Wait for a few minutes for the images to build and services to start.
    *   Verify they are running: `docker ps`

3.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download NLTK Data**:
    The system requires the CMU Pronouncing Dictionary.
    ```bash
    python -c "import nltk; nltk.download('cmudict')"
    ```

## Running the Application

1.  **Start the Backend API**:
    This is the main application that serves the frontend and orchestrates the scoring.
    ```bash
    python api/app.py
    ```
    *   The server will start on `http://0.0.0.0:5000`.

2.  **Access the Application**:
    *   Open your web browser.
    *   Navigate to **[http://localhost:5000](http://localhost:5000)**.

## Usage

*   **Read Aloud**: Practice reading text with pronunciation scoring.
*   **Repeat Sentence**: Listen to audio and repeat it.
*   **Describe Image**: Describe the displayed image (uses ASR + Grammar check).
*   **Retell Lecture**: Listen to a lecture and summarize it.

## Troubleshooting

*   **"docker-compose" not found**: Ensure Docker Desktop is installed. On newer versions, use `docker compose` (no hyphen) instead.
*   **Audio Conversion Failed**: Ensure `ffmpeg` is installed correctly. Run `ffmpeg -version` in a new terminal to check.
*   **Port Conflicts**:
    *   Ensure ports `5000`, `8000`, and `8001` are free.
    *   If `8000` is taken, you need to change it in `docker-compose.yml` AND `api/app.py` (`GRAMMAR_SERVICE_URL`).
*   **Permission Errors (Docker)**: On Linux/Mac, you might need `sudo`. On Windows, ensure Docker Desktop is running.
