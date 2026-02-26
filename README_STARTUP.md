# PTE Platform Startup Guide (Current System)

This document replaces the old startup guide and matches the current repository setup.

## 1) Current architecture

The platform runs 3 services:

- `api` (Flask web app): `http://localhost:5000`
- `asr-grammar` (ASR + grammar microservice): `http://localhost:8000`
- `wav2vec2-service` (phoneme microservice): `http://localhost:8001`

Runtime data is stored in `./data` and mounted into containers.

Important: Read Aloud MFA alignment is executed through Docker from the API runtime. When API runs in Docker, `PTE_HOST_PROJECT_ROOT` must be set correctly in `.env`.

## 2) Prerequisites

### Required for Docker-first setup (recommended)

- Docker Engine
- Docker Compose plugin (`docker compose`)
- Git

### Required only if you run API directly on host

- Python 3.10+
- `pip` and `venv`
- `ffmpeg`

### Arch Linux install example

```bash
sudo pacman -Syu
sudo pacman -S docker docker-compose git python python-pip python-virtualenv ffmpeg
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

### Verify tools

```bash
docker --version
docker compose version
git --version
python --version
ffmpeg -version
```

## 3) Project bootstrap

From your workspace root:

```bash
cd /home/sushil/developer/pte/PTE
```

Create environment file:

```bash
cp .env.example .env
```

Set absolute host path in `.env`:

```bash
PTE_HOST_PROJECT_ROOT=/home/sushil/developer/pte/PTE
```

This is required for MFA bind mounts when API runs in container.

Ensure runtime directories exist (safe to run always):

```bash
mkdir -p data/user_uploads data/processed/mfa_runs data/models/mfa
```

## 4) Start full stack with Docker (recommended)

```bash
docker compose up -d --build
```

Check container status:

```bash
docker compose ps
```

Expected container names:

- `pte-api`
- `pte-asr-grammar-service`
- `wav2vec2-phoneme-cpu`

## 5) Verify startup

Run health/smoke checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:5000/
```

If all respond, open:

- `http://localhost:5000`

## 6) Logs and lifecycle commands

```bash
# Follow logs
docker compose logs -f --tail=200 api
docker compose logs -f --tail=200 asr-grammar
docker compose logs -f --tail=200 wav2vec2-service

# Stop
docker compose down

# Restart
docker compose restart api

# Rebuild only API after code/dependency/Dockerfile changes
docker compose build api
docker compose up -d api
```

## 7) Startup diagnostics

You can run diagnostics from host Python or inside the API container.

From host:

```bash
python -m api.startup_diagnostics
```

From API container:

```bash
docker compose exec api python -m api.startup_diagnostics
```

Report includes:

- import/module checks
- required directory checks
- ASR and phoneme health checks
- Docker CLI availability

## 8) Fast development mode (live code mounts)

Use compose override for rapid iteration:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Behavior:

- Python/template/source edits are reflected quickly
- rebuild required only for dependency/system image changes

Rebuild API in dev mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build api
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api
```

## 9) Alternative mode: API on host, model services in Docker

Use this only if needed.

Start microservices in Docker:

```bash
docker compose up -d asr-grammar wav2vec2-service
```

Prepare host Python env:

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -c "import nltk; nltk.download('cmudict')"
```

Run Flask API on host:

```bash
python api/app.py --port 5000
```

Then open `http://localhost:5000`.

## 10) Startup-critical environment variables

- `PTE_HOST_PROJECT_ROOT`
  Required when API runs in Docker and launches MFA containers.

- `PTE_MFA_DOCKER_MOUNT_BASE_DIR`
  Optional explicit override for MFA model mount source.

- `PTE_MFA_DOCKER_MOUNT_RUNTIME_DIR`
  Optional explicit override for MFA runtime mount source.

- `PTE_SKIP_MFA`
  Set `1` to skip MFA and return ASR-only analysis fallback.

- `PTE_MFA_NUM_JOBS`
  Optional MFA parallel jobs override.

- `PTE_READ_ALOUD_CACHE_ENABLED`
  Enable/disable Read Aloud result cache (`1` by default).

- `PTE_READ_ALOUD_CACHE_MAX_AGE_SECONDS`
  Cache TTL (default 7 days).

- `PTE_KEEP_UPLOAD_ARTIFACTS`
  Keep uploaded/generated artifacts (`1` by default).

## 11) Troubleshooting

### MFA alignment fails or falls back to ASR-only

Check Docker from the same runtime where API executes:

```bash
docker info
docker ps
```

Inspect MFA stderr logs:

```bash
ls -1t data/processed/mfa_runs | head
# then inspect latest run
# data/processed/mfa_runs/<run_id>/output/<accent>/mfa_stderr.log
```

### MFA bind mount/path errors

- Confirm `.env` has correct absolute `PTE_HOST_PROJECT_ROOT`.
- Confirm these exist on host:
  - `data/models/mfa`
  - `data/processed/mfa_runs`

### API cannot reach ASR/phoneme services

```bash
docker compose ps
docker compose logs --tail=200 api
docker compose logs --tail=200 asr-grammar
docker compose logs --tail=200 wav2vec2-service
```

### Port already in use

```bash
ss -tulpn | grep :5000
ss -tulpn | grep :8000
ss -tulpn | grep :8001
```

### Docker permission denied

Use Docker group access instead of opening socket permissions:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 12) Minimal quick start

```bash
cd /home/sushil/developer/pte/PTE
cp .env.example .env
# edit .env: set PTE_HOST_PROJECT_ROOT to this absolute path

docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:5000/
```

If these checks pass, the current system is running correctly.
