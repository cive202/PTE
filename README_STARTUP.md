# 🚀 PTE Platform Setup Guide

Follow these steps to set up the platform on a fresh system.

---

## 1. Install System Tools

Install the core requirements for your operating system.

**For Arch Linux:**

```bash
sudo pacman -S git python ffmpeg docker docker-compose
```

### Configure Docker

Start the Docker engine and grant user permissions.

```bash
# Start and enable Docker
sudo systemctl enable --now docker

# Grant user permissions (Log out and back in after running this)
sudo usermod -aG docker $USER
```

---

## 2. Prepare the Project

Clone the repository and set up the Python environment.

```bash
# Clone the repository
git clone <your-repo-url>
cd PTE

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

---

## 3. Start AI Services

Launch the background services for speech and grammar using Docker.

```bash
# Enter Docker directory
cd PTE_ASR_GRAMMAR_DOCKER

# Build and start services
docker-compose up -d --build

# Return to root directory
cd ..
```

---

## 4. Launch the Platform

Start the main application.

```bash
# Run the startup script
./test/startup.sh

# Or run manually
# python api/app.py
```

**Access the UI at:** [http://localhost:5000](http://localhost:5000)

---

## 💡 Quick Fixes

* **Mic issues:** Grant browser permissions and check system input settings.
* **Missing data:** Run `python -c "import nltk; nltk.download('cmudict'); nltk.download('punkt')"`
* **Logs:** Run `docker logs pte-asr-grammar-service` to debug AI services.
