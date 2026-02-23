# PTE Practice Platform - Simple Setup (New System)

This guide explains how to bring the full platform up on a clean machine in simple, technical steps. It assumes you will run everything with Docker Compose (recommended).

## What runs where (simple)

Based on the screenshots provided:

- **API (Flask)**: `sushil346/pte-api` (Port 5000)
- **ASR/Grammar**: `sushil346/pte-asr-grammar` (Port 8000)
- **Phoneme**: `sushil346/wav2vec2-phoneme-cpu` (Port 8001)

## 1) Install prerequisites

### Update system

```bash
sudo pacman -Syu
```

### Install required packages

```bash
sudo pacman -S python python-pip python-virtualenv git ffmpeg docker docker-compose

# Enable and start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect, or run:
newgrp docker
```

### Verify installs

```bash
# Check Python version (should be 3.10+)
python --version

# Check Docker
docker --version
docker-compose --version

# Check FFmpeg
ffmpeg -version

# Check Git
git --version
```

## 2) Get the code

```bash
git clone https://github.com/cive202/PTE.git
cd PTE
```

## 3) Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and set your absolute project path:

```bash
PTE_HOST_PROJECT_ROOT=/absolute/path/to/PTE
```

Example:

```bash
PTE_HOST_PROJECT_ROOT=/home/youruser/PTE
```

## 4) Start everything with Docker

```bash
docker compose up -d --build
```

## 5) Verify services

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:5000/
```

If all three return OK/200, the system is up.

## Troubleshooting (quick)

If API cannot reach ASR/Phoneme:

```bash
docker compose ps
docker compose logs --tail=200 api
```

If MFA paths fail, re-check `PTE_HOST_PROJECT_ROOT` in `.env`.

## Full detailed guide

See `docs/operations/NEW_SYSTEM_SETUP.md` for a longer, step-by-step version.

### 2. End-to-End Test

1. Open the web UI
2. Try a "Read Aloud" or "Repeat Sentence" task
3. Record or upload audio
4. Verify that:
   - Audio is processed
   - Results are returned from microservices
   - Scoring displays correctly

### 3. Check Service Endpoints

```bash
# Check all services are responding
curl http://localhost:5000/  # Main app
curl http://localhost:8000/health  # ASR service
curl http://localhost:8001/health  # Phoneme service
```

## Troubleshooting

### Docker Issues

```bash
# Restart Docker daemon
sudo systemctl restart docker

# Remove and rebuild containers
docker-compose down
docker-compose up -d --force-recreate

# View container logs
docker logs pte-asr-grammar
docker logs pte-phoneme-cpu
```

### Port Conflicts

```bash
# Check what's using a port
sudo netstat -tulpn | grep :5000
sudo netstat -tulpn | grep :8000
sudo netstat -tulpn | grep :8001

# Or using ss
sudo ss -tulpn | grep :5000
```

### Python Environment Issues

```bash
# Deactivate and recreate virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Permission Issues

```bash
# If Docker permission denied
sudo chmod 666 /var/run/docker.sock

# Or ensure user is in docker group
groups $USER
# Should show 'docker' in the list
```

## Useful Commands

### Docker Management

```bash
# Stop all services
docker-compose down

# Start services
docker-compose up -d

# Restart a specific service
docker-compose restart asr-grammar

# View resource usage
docker stats

# Clean up unused images/containers
docker system prune -a
```

### Application Management

```bash
# Activate virtual environment
source venv/bin/activate

# Deactivate virtual environment
deactivate

# Update dependencies
pip install -r requirements.txt --upgrade

# Freeze current dependencies
pip freeze > requirements.txt
```

## Systemd Service (Optional)

To run the application as a system service:

```bash
# Create service file
sudo nano /etc/systemd/system/pte-platform.service
```

Add this content:

```ini
[Unit]
Description=PTE Practice Platform
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/PTE/api
Environment="PATH=/path/to/PTE/venv/bin"
ExecStart=/path/to/PTE/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pte-platform
sudo systemctl start pte-platform
sudo systemctl status pte-platform
```

## Project Structure Reference

```
PTE/
├── api/
│   ├── app.py              # Main Flask application
│   └── ...
├── venv/                   # Virtual environment
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker services configuration
└── README.md              # Project documentation
```

## Quick Start Summary

```bash
# 1. Install prerequisites (one-time)
sudo pacman -S python python-pip docker docker-compose ffmpeg git

# 2. Setup Docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

# 3. Setup project
cd ~/PTE
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "import nltk; nltk.download('cmudict')"

# 4. Start Docker services
docker-compose up -d

# 5. Start Flask app
cd api
python app.py

# 6. Access at http://localhost:5000
```

## Support & Logs

When asking for help, provide:

```bash
# System info
uname -a
python --version
docker --version

# Docker logs
docker-compose logs

# Application logs
cat api/logs/*.log  # if logging to file
```

---
