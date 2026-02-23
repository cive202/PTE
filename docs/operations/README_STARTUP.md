# PTE Practice Platform - Simple Setup (New System)

This guide explains how to bring the full platform up on a clean machine in simple, technical steps. It assumes you will run everything with Docker Compose (recommended).

## What runs where (simple)

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

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
```

### Verify installs

```bash
python --version

docker --version
docker-compose --version

ffmpeg -version

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
