# Presentation Script and Demo Checklist

## Purpose

This is a ready script for you and your friend.

Use it for:

1. Internal management presentation.
2. Client discovery/demo meeting.
3. Pilot approval discussion.

## 15-Minute Talk Track (Simple Script)

## Minute 0-2: Open

Say:

"We built a PTE speaking evaluation platform that gives consistent, explainable scoring.  
It reduces manual effort and improves turnaround speed."

## Minute 2-4: Problem

Say:

"Current manual process has three main issues: inconsistency, delay, and scaling cost.  
Our system standardizes evaluation and gives detailed feedback."

## Minute 4-7: Product Walkthrough

Show:

1. Main UI flow.
2. One speaking task submission.
3. Returned analysis and feedback view.

Say:

"The result includes transcription, pronunciation-level signals, and structured scoring support."

## Minute 7-9: Technical Reliability

Say:

"Services run in containers for portability.  
Current architecture includes ASR and phoneme services; API and MFA runner are being standardized into managed container flow."

## Minute 9-11: Deployment Choices

Say:

"We can deploy on your company infrastructure first, and scale in AWS using managed services when volume grows."

## Minute 11-13: Security and Operations

Say:

"We control access, keep audit logs, define retention, and separate persistent data from application images."

## Minute 13-15: Ask

Say:

"We propose a 4-week pilot with agreed KPIs and a go/no-go review at the end."

## Live Demo Checklist (before meeting)

Run these checks before every demo.

1. Containers up and healthy.
2. Test audio file available.
3. At least one successful sample result prepared.
4. Fallback plan if internet/audio device fails.
5. Logs open in second terminal for troubleshooting.

## Suggested Pre-demo Commands

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8001/health
```

If API is containerized:

```bash
curl http://localhost:5000/
```

## Q&A Bank (use in meetings)

## Q1: "Can this run on our private infrastructure?"

Answer:

"Yes. It can run on a company server using Docker. No mandatory external SaaS dependency is required for core flow."

## Q2: "Can this scale?"

Answer:

"Yes. Initial deployment can be single-node. For scale, we move to AWS ECS with load balancing and managed logs."

## Q3: "How is data protected?"

Answer:

"We keep runtime data in controlled storage, enforce access control, and can apply retention/deletion policies per customer."

## Q4: "How do updates happen?"

Answer:

"Versioned container images are released and deployed with rollback tags. We do staged rollout: test -> staging -> production."

## Q5: "What if a model/service fails?"

Answer:

"Health checks and restart policies are used. We also maintain logs and fallback handling to reduce user-facing disruption."

## Pilot Proposal Template

Use this exact format:

1. Duration: 4 weeks.
2. Scope: Selected speaking modules.
3. KPI: success rate, latency, reviewer time saved.
4. Infra: customer server or AWS account.
5. Exit criteria: KPI achievement + stakeholder sign-off.

## Post-Meeting Follow-up Template

Subject: `PTE Evaluation Platform - Pilot Proposal and Next Steps`

Body:

1. Thank you note.
2. One-paragraph summary of value.
3. Proposed pilot scope and timeline.
4. Required access/infrastructure from their side.
5. Proposed next meeting date.

## Simple explanation of this document

This document gives you:

1. What to say in each minute of the presentation.
2. What to check before live demo.
3. Ready answers for common management/client questions.
4. A standard pilot ask and follow-up method.

