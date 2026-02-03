# Build and Setup Plan for PTE Practice Platform (Windows Adaptation)

This plan outlines the steps to adapt and set up the PTE practice platform on your Windows machine, moving from its original Arch Linux configuration.

## Technical Implementation

### 1. Environment & Dependencies
- **Python Setup**: Create a virtual environment and install dependencies from `requirements.txt`.
- **NLTK Data**: Download required models (`cmudict`, `punkt`) for phonetic analysis.
- **FFmpeg**: Ensure FFmpeg is installed and added to the system PATH (required for audio conversion in `api/app.py`).

### 2. ASR & Grammar Service (Docker)
- **Containerization**: Use the existing `PTE_ASR_GRAMMAR_DOCKER` to build the Whisper ASR and LanguageTool service.
- **Execution**: Run `build_and_run_docker.ps1` to automate the build and startup process on port 8000.

### 3. Montreal Forced Aligner (MFA) Setup
- **Local Installation**: Instead of the Docker-based MFA (which has pathing issues on Windows), we will use a local MFA installation via Conda as recommended in `INSTALL_MFA.md`.
- **Model Downloads**: Download the `english_us_arpa` acoustic model and dictionary using MFA commands.
- **Code Refactor**: Update `api/validator.py` to use the robust alignment logic in `pte_core/mfa/aligner.py` instead of the hardcoded Docker path.

### 4. Application Launch
- **Startup Script**: Create a `startup.ps1` script to automate the launch of the Flask application on port 5000.
- **Verification**: Verify the connection between the Flask app and the Docker ASR service.

## Milestone

### Phase 1: Core Services
1. Build and start the ASR Docker container.
2. Install Python dependencies and NLTK data.

### Phase 2: Alignment Engine
1. Install MFA via Conda.
2. Refactor `api/validator.py` to use local MFA.

### Phase 3: Launch & Test
1. Start the Flask application.
2. Perform a test "Read Aloud" task to verify end-to-end functionality.

**Would you like me to proceed with these steps?**
