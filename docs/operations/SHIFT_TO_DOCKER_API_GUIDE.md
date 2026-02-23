# Shift Flask API to Docker (Step-by-Step)

## What changed

This repo now supports running the main Flask API inside Docker Compose.

Added:

1. `docker/api/Dockerfile`
2. `api` service in `docker-compose.yml`
3. `.env.example` for MFA host mount mapping
4. MFA mount-source mapping support in `api/validator.py`

## Why this is needed

Before:

1. ASR (`8000`) and phoneme (`8001`) were in Docker.
2. Main API (`5000`) ran on host Python.

Now:

1. API can run in Docker too.
2. All runtime libraries are in container image.
3. Setup is more standard for handover/sales.

## Important MFA note

Current MFA flow still runs via `docker run` from API code.

Because API is now in a container, it needs:

1. Docker socket mount (`/var/run/docker.sock`)  
2. Host project absolute path in `.env` (`PTE_HOST_PROJECT_ROOT`)

This is transitional. Next step is dedicated `mfa-runner` service.

## Setup steps

## 1) Create `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```bash
PTE_HOST_PROJECT_ROOT=/your/absolute/path/to/PTE
```

Example:

```bash
PTE_HOST_PROJECT_ROOT=/home/sushil/developer/pte/PTE
```

## 2) Build and start all services

```bash
docker compose up -d --build
```

## 3) Verify services

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:5000/
```

## 4) View logs

```bash
docker compose logs -f --tail=200 api
docker compose logs -f --tail=200 asr-grammar
docker compose logs -f --tail=200 wav2vec2-service
```

## Simple explanation of what is happening

1. API talks to ASR/phoneme using internal Docker network names.
2. API writes user/runtime data into mounted `./data`.
3. For MFA, API asks host Docker daemon to start alignment container.

## Troubleshooting

## MFA fails with mount/path errors

Check:

1. `.env` has correct `PTE_HOST_PROJECT_ROOT`.
2. Host paths exist:
   - `${PTE_HOST_PROJECT_ROOT}/data/models/mfa`
   - `${PTE_HOST_PROJECT_ROOT}/data/processed/mfa_runs`

## API cannot reach ASR/phoneme

Check:

1. `docker compose ps` shows all services `Up`.
2. API env variables in compose:
   - `PTE_ASR_GRAMMAR_BASE_URL=http://asr-grammar:8000`
   - `PTE_PHONEME_BASE_URL=http://wav2vec2-service:8001`

## Next standardization step

Replace MFA shell-based docker orchestration with a dedicated `mfa-runner` service.
