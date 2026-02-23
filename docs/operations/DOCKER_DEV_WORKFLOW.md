# Docker Dev Workflow (Fast Changes)

Use this during active development so you do not rebuild for every small edit.

## Why this mode

- Your normal `docker-compose.yml` runs from built images.
- Without code bind mounts, local file changes are not visible until rebuild.
- Dev mode bind-mounts source into container, so edits show up quickly.

## Start Dev Mode

From project root:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This starts:
- `api` on `5000` with live source mounts
- `asr-grammar` on `8000`
- `wav2vec2-service` on `8001`

## Day-to-day editing behavior

- `api/templates/*.html`, CSS, JS: refresh browser.
- `api/*.py`, `pte_core/*.py`, `src/*.py`: Flask debug server auto-reloads.
- `data/reference/*.json`: picked up on next request for most flows.

## When rebuild is required

Rebuild only if you change:
- `requirements.txt`
- `docker/api/Dockerfile`
- system packages / apt installs

Rebuild command:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build api
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api
```

## Final production-style run (no source mounts)

When ready to release:

```bash
docker compose down
docker compose -f docker-compose.yml up -d --build
```

## Push final images

```bash
docker push sushil346/pte-api:latest
docker push sushil346/pte-asr-grammar:latest
docker push sushil346/wav2vec2-phoneme-cpu:latest
```

Tag with commit too:

```bash
git rev-parse --short HEAD
docker tag sushil346/pte-api:latest sushil346/pte-api:<commit>
docker push sushil346/pte-api:<commit>
```

