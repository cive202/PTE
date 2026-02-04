# 🐳 PTE System Docker Setup Guide

This project is fully Dockerized to ensure it runs consistently on any machine (Windows, Mac, Linux) without Python version conflicts.

## 📋 Prerequisites (Arch Linux)
1.  **Git**: `sudo pacman -S git`
2.  **Docker**:
    ```bash
    sudo pacman -S docker docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    # Add your user to the docker group (so you don't need sudo for docker commands)
    sudo usermod -aG docker $(whoami)
    newgrp docker
    ```

## 🚀 How to Run on a New Machine

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd PTE
```

### 2. Start the System
Run the following command in your terminal (inside the `PTE` folder):

```bash
docker-compose up --build
```

*   **First Run**: This will take a few minutes to download images and build the containers.
*   **Subsequent Runs**: It will start almost instantly.

### 3. Access the Application
Once you see logs saying `Running on http://0.0.0.0:5000`, open your browser:

*   **Main App**: [http://localhost:5000](http://localhost:5000)

## 🛠️ What's Happening Behind the Scenes?
*   **pte-web**: Your main Flask application (Python 3.10).
*   **pte-asr-grammar**: A dedicated service for Speech Recognition (Parakeet) and Grammar checking.
*   **MFA (On-Demand)**: When you submit a request, the app spins up temporary Docker containers to run the Montreal Forced Aligner using the `Indian` or `US` models.

## 🛑 Stopping the System
Press `Ctrl+C` in the terminal, or run:
```bash
docker-compose down
```

## ⚠️ Troubleshooting
*   **Port Conflicts**: If port 5000 or 8000 is in use, edit `docker-compose.yml` to change the mapping (e.g., `"5001:5000"`).
*   **Memory**: ASR models can be heavy. Ensure Docker has access to at least 4GB-8GB of RAM in Docker Desktop settings.
