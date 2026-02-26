# Deployment Guide (Free, Small Usage)

## Context (This Repo)

This project is **not** a simple frontend + backend app. It currently runs as a **3-service Docker Compose stack**:

- `api` (Flask UI + API)
- `asr-grammar` (NeMo/ASR service)
- `wav2vec2-service` (phoneme service)

Also, some speaking flows can trigger MFA-related behavior that depends on Docker runtime behavior.

Because of this, generic advice like "frontend on Vercel + backend on free API host" is usually a mismatch.

## Short Answer

For your current codebase and usage level (3-4 people testing), the best free approach is:

1. **Run the existing Docker Compose stack on one Linux host you control** (local spare machine or small cloud VM).
2. Expose it with:
   - public IP + reverse proxy, or
   - Cloudflare Tunnel (free) for easy secure access.

This avoids refactoring and keeps your architecture intact.

## Why Most "Free PaaS Split" Advice Fails Here

- Your UI is served by Flask templates already, so separate static hosting is optional, not required.
- You need multiple backend services, not one tiny API container.
- Free PaaS tiers are typically small and/or sleeping:
  - Render free web services spin down after 15 min idle and have monthly free-hour limits.
  - Koyeb free includes only one free web service and low memory.
  - Railway is not truly free long-term (trial + paid floor).

## Recommended Options

## Option A (Recommended): Self-host Compose + Cloudflare Tunnel (Free)

Best when you have one machine that can stay online.

### Pros

- Truly free in platform fees
- No architecture rewrite
- No container split complexity
- Good enough for 3-4 testers

### Cons

- Your machine/VM must stay online
- You handle ops basics (updates, restarts, logs)

### Steps

1. Provision host with Docker + Compose.
2. Clone repo and configure `.env` (`PTE_HOST_PROJECT_ROOT` etc., same as local guide).
3. Run:

```bash
docker compose up -d --build
```

4. Validate:

```bash
curl http://localhost:5000/
curl http://localhost:8000/health
curl http://localhost:8001/health
```

5. Expose app:
   - simplest: Cloudflare Tunnel to `http://localhost:5000`
   - alternative: reverse proxy + TLS on VM public IP/domain

## Option B: Oracle Cloud Always Free VM + Docker Compose

If you want cloud-hosted and still free, this is the strongest candidate.

### Important caveat

- Always Free Ampere is ARM-based. Your ML/image dependencies may require validation on ARM.
- If ARM compatibility blocks you, this stops being a clean "free" path.

### Steps (high-level)

1. Create OCI Always Free compute instance.
2. Install Docker + Compose.
3. Deploy same Compose stack.
4. Open only required ports / use tunnel.

## Not Recommended (for this repo, without refactor)

- **Render free** for all services: sleep + free-hour constraints and multi-service overhead.
- **Koyeb free** as a full replacement: one free service with low memory is too tight for this stack.
- **Railway free** as "forever free": current pricing is trial-first and then paid.

## Minimal Hardening Checklist

- Keep `docker compose` services pinned and restart policy enabled.
- Add basic auth/rate-limit if exposed publicly.
- Restrict inbound network ports.
- Keep `data/` on persistent disk and back it up periodically.
- Add uptime check (simple cron + curl or external monitor).

## Suggested Practical Path (What I’d Do)

1. Deploy current stack unchanged on one Linux host.
2. Give testers one HTTPS URL via Cloudflare Tunnel.
3. Run 1 week with real usage.
4. Measure memory/CPU and then decide:
   - stay free self-hosted, or
   - move to paid managed infra if reliability/SLA matters.

## References (Checked February 26, 2026)

- Render free limitations: https://render.com/docs/free
- Render free overview: https://render.com/free
- Koyeb pricing/free FAQ: https://www.koyeb.com/pricing
- Koyeb compose tutorial (privileged compose pattern): https://www.koyeb.com/tutorials/deploy-apps-using-docker-compose-on-koyeb
- Railway pricing: https://railway.com/pricing
- Railway pricing FAQ: https://docs.railway.com/reference/pricing/faqs
- Oracle Free Tier overview: https://www.oracle.com/cloud/free/
- Oracle Always Free resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Cloudflare Tunnel product page: https://www.cloudflare.com/products/tunnel/
