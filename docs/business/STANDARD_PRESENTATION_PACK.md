# Standard Presentation Pack (Company + Client Ready)

## Purpose

Use this structure every time you present the platform to management, internal IT, or external clients.

Goal: make the product look reliable, commercial, and deployment-ready.

## Audience Types

Present differently based on who is in the room.

1. Business leadership: value, ROI, timeline, risk.
2. Engineering/IT: architecture, deployment, support model.
3. Compliance/security: data handling, access control, audit.
4. End users/operations: usability, reporting, turnaround time.

## Standard 12-Slide Flow

Use this order. Do not skip.

1. Title + One-line value
   - Example: "AI-powered PTE speaking evaluation with explainable scoring."
2. Problem statement
   - Manual scoring is slow, inconsistent, costly.
3. Solution summary
   - Automated scoring, accent-aware analysis, structured feedback.
4. Product modules
   - Read Aloud, Repeat Sentence, Describe Image, Retell Lecture.
5. How scoring works (simple)
   - ASR + phoneme analysis + pause/fluency + grammar signals.
6. Architecture (current + standard target)
   - API, ASR service, phoneme service, MFA runner, data store.
7. Deployment options
   - Company server (Docker Compose), AWS (EC2 now, ECS later).
8. Security and governance
   - Auth, HTTPS, retention policy, logs, backups.
9. Performance and quality metrics
   - Response time, success rate, scoring consistency.
10. Rollout plan
   - Pilot -> hardening -> production.
11. Commercial model
   - License + support + upgrade plan.
12. Ask / next step
   - Pilot approval, infra owner, timeline sign-off.

## What Evidence to Show (important)

Do not only "tell"; show proof.

1. Running services health endpoints.
2. Real demo with one spoken attempt.
3. Word-level or phoneme-level feedback output.
4. Deployment docs from `docs/operations/`.
5. Planned architecture roadmap (API in Docker + MFA runner service).

## Message Discipline (what to say repeatedly)

Use these exact themes:

1. "Standardized scoring and explainable feedback."
2. "Containerized, portable deployment."
3. "Can run on company infra or AWS."
4. "Pilot-first, measurable KPI rollout."

## KPI Targets for Pilot Slide

Use measurable targets:

1. End-to-end processing success rate: `>= 95%`.
2. P95 turnaround time per submission: `< 120s` (target after tuning).
3. Platform uptime during pilot window: `>= 99%`.
4. Manual review effort reduction: `>= 40%` (baseline-dependent).

## Delivery Models to Present

1. Internal deployment only.
2. White-label B2B deployment.
3. Managed service by your company.

For each model, clearly state:

1. Who hosts.
2. Who supports.
3. Who owns data.
4. SLA and update cadence.

## Common Mistakes to Avoid in Presentation

1. Too much model-level jargon in first 5 minutes.
2. No clear deployment story.
3. No data retention/security answer.
4. No pilot timeline with owner names.
5. Saying "we are still figuring out everything."

## One-Sentence Close

"We can start with a controlled pilot in your environment, measure outcomes with agreed KPIs, and move to production with a clear support and security model."

