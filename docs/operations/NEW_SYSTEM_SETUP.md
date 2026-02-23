# New System Setup (Simple Technical Guide)

This document explains how to install and start the full PTE platform on a clean machine.

## What you will run

- `sushil346/pte-api` (Flask API, Port 5000)
- `sushil346/pte-asr-grammar` (ASR + Grammar, Port 8000)
- `sushil346/wav2vec2-phoneme-cpu` (Phoneme, Port 8001)

All three run with Docker Compose.

## 1) Install required software

Arch Linux:

```bash
sudo pacman -Syu
sudo pacman -S python python-pip python-virtualenv git ffmpeg docker docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
```

If you are not on Arch, install:

- Python 3.10+
- Git
- FFmpeg
- Docker + Docker Compose

## 2) Download the project

```bash
git clone https://github.com/cive202/PTE.git
cd PTE
```

## 3) Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your absolute project path:

```bash
PTE_HOST_PROJECT_ROOT=/absolute/path/to/PTE
```

This is required because the API starts MFA alignment containers and must mount host paths correctly.

## 4) Start the platform

```bash
docker compose up -d --build
```

## 5) Verify it is working

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:5000/
```

If all three respond, the system is up.

## 6) Basic operations

Stop:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f --tail=200 api
docker compose logs -f --tail=200 asr-grammar
docker compose logs -f --tail=200 wav2vec2-service
```

## Troubleshooting

`docker compose ps` shows a container not running:

```bash
docker compose logs --tail=200 <service-name>
```

API cannot reach ASR/Phoneme:

- Confirm the containers are Up.
- Check API env in `docker-compose.yml`:
  - `PTE_ASR_GRAMMAR_BASE_URL=http://asr-grammar:8000`
  - `PTE_PHONEME_BASE_URL=http://wav2vec2-service:8001`

MFA path errors:

- Confirm `.env` has correct `PTE_HOST_PROJECT_ROOT`.
- Confirm host folders exist:
  - `data/models/mfa`
  - `data/processed/mfa_runs`
