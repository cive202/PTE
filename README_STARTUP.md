# How to Run the PTE Scoring Engine

This guide provides step-by-step instructions to set up and run the PTE Scoring Engine on your local machine.

## Prerequisites

1.  **Docker Desktop**: 
    *   Must be installed and running.
    *   Required for:
        *   MFA Alignment (runs transient containers).
        *   ASR/Grammar Service (runs a persistent container).
2.  **Python 3.8+**: Ensure Python is installed and added to your PATH.
3.  **FFmpeg**: 
    *   Must be installed and accessible via command line (`ffmpeg -version`).
    *   Used by the backend to convert audio to 16kHz WAV format.

## Installation

1.  **Open a terminal** in the project root directory:
    ```powershell
    cd C:\Users\Acer\DataScience\PTE
    ```

2.  **Install Python Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

3.  **Download NLTK Data**:
    The system requires the CMU Pronouncing Dictionary.
    ```powershell
    python -c "import nltk; nltk.download('cmudict')"
    ```

## Running the Application

The application consists of two main parts: the **ASR/Grammar Service** (Docker) and the **Backend API** (Python/Flask).

### Step 1: Start the ASR/Grammar Service
This service runs in a Docker container on port `8000`. It handles Speech-to-Text (Whisper) and Grammar checking.

1.  Run the helper script:
    ```powershell
    .\build_and_run_docker.ps1
    ```
2.  Wait for the script to complete. It will print "Service Status: ok" when ready.

### Step 2: Start the Backend API
This is the main application that serves the frontend and orchestrates the scoring.

1.  Open a **new terminal window** (keep the previous one open).
2.  Run the Flask application:
    ```powershell
    python api/app.py
    ```
3.  The server will start on `http://0.0.0.0:5000`.

## Usage

1.  Open your web browser.
2.  Navigate to **[http://localhost:5000](http://localhost:5000)**.
3.  You can now:
    *   **Record Audio**: Use the microphone button to record your speech.
    *   **Upload Audio**: Upload an existing audio file.
    *   **Get Scores**: The system will process the audio using MFA and the ASR service to provide pronunciation and fluency scores.

## Troubleshooting

*   **Docker Errors**: Ensure Docker Desktop is running. If you see "daemon not running" errors, start Docker Desktop and try again.
*   **Audio Conversion Failed**: Ensure `ffmpeg` is installed. Try running `ffmpeg` in your terminal to verify.
*   **Port Conflicts**: 
    *   The ASR service uses port `8000`.
    *   The Flask app uses port `5000`.
    *   Ensure these ports are not used by other applications.
