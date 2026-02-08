# PTE Practice Platform - Arch Linux Setup Guide

This guide will help you set up the PTE Practice Platform on your Arch Linux system. The platform consists of a Flask application and two AI microservices running in Docker.

## System Architecture Overview

Based on the screenshots provided:

- **Main Application**: Flask backend (Port 5000)
- **ASR/Grammar Service**: Docker container `cive202/pte-asr-grammar` (Port 8000)
- **Phoneme Analysis Service**: Docker container `cive202/wav2vec2-phoneme-cpu` (Port 8001)

## Prerequisites Installation

### 1. Update System

```bash
sudo pacman -Syu
```

### 2. Install Required Packages

```bash
# Install Python 3.10+ and pip
sudo pacman -S python python-pip python-virtualenv

# Install Git
sudo pacman -S git

# Install FFmpeg (required for audio processing)
sudo pacman -S ffmpeg

# Install Docker and Docker Compose
sudo pacman -S docker docker-compose

# Enable and start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect, or run:
newgrp docker
```

### 3. Verify Installations

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

## Project Setup

### 1. Navigate to Project Directory

```bash
cd ~/PTE
# Or wherever your project is located
```

### 2. Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate

# Your prompt should now show (venv)
```

### 3. Install Python Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Download NLTK data for pronunciation scoring
python -c "import nltk; nltk.download('cmudict')"
```

## Docker Services Setup

### 1. Pull Docker Images

The screenshots show you already have these images on Docker Hub. Pull them:

```bash
# Pull ASR/Grammar service
docker pull cive202/pte-asr-grammar

# Pull Phoneme analysis service
docker pull cive202/wav2vec2-phoneme-cpu
```

### 2. Create Docker Compose File

If you don't already have a `docker-compose.yml`, create one:

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  asr-grammar:
    image: cive202/pte-asr-grammar
    container_name: pte-asr-grammar
    ports:
      - "8000:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  phoneme-cpu:
    image: cive202/wav2vec2-phoneme-cpu
    container_name: pte-phoneme-cpu
    ports:
      - "8001:8001"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  default:
    name: pte-network
EOF
```

### 3. Start Docker Services

```bash
# Build and start services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 4. Verify Services are Running

```bash
# Check ASR/Grammar service (Port 8000)
curl http://localhost:8000/health
# or visit http://localhost:8000/docs in browser

# Check Phoneme service (Port 8001)
curl http://localhost:8001/health

# Check Docker container status
docker ps
```

Expected output should show both containers running.

## Launch Main Application

### 1. Ensure Virtual Environment is Active

```bash
# If not already activated:
source venv/bin/activate
```

### 2. Start Flask Application

```bash
# Navigate to api directory if needed
cd api

# Start the Flask application
python app.py
```

The application should start on `http://localhost:5000`

### 3. Alternative: Run with Gunicorn (Production)

For better performance:

```bash
# Install gunicorn if not in requirements.txt
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Validation & Testing

### 1. Access the Application

Open your browser and navigate to:

```
http://localhost:5000
```

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
