# ADR-001: Architecture Baseline

## Status

Accepted

## Context

The system must support:

- Institutional medical shift planning with strict domain rules
- Operator workflows via panel and Telegram NL
- Automated WhatsApp notifications
- Traceability and reports
- Cost-aware operation and anti-hallucination behavior

## Decision

- Backend: FastAPI (Python)
- Database: PostgreSQL
- MVP scheduling: Railway Cron + PostgreSQL-backed scheduled jobs
- Advanced workers/queues: Celery + Redis when continuous background processing is required
- Optimization: OR-Tools CP-SAT
- Operator channel: Telegram NL assistant using DeepSeek
- Doctor channel: Twilio WhatsApp notifications (initial + 12h reminder)
- Frontend: React + Vite (PWA-ready)
- Production hosting: Railway for backend/data services, Vercel for frontend
- Local development: Docker Compose

## Consequences

- Fast iteration with clear API contracts
- Good fit for domain-heavy scheduling logic
- Managed LLM cost with strict tool grounding
- Requires robust guardrails and fallback policy
- MVP can minimize idle compute cost by using short-lived scheduled jobs instead of always-on workers
- Celery/Redis remains available as an evolution path for high-volume or near-real-time background work

## Follow-up Decisions

- `ADR-002-modular-monolith-design-patterns.md` defines the modular monolith implementation style and design patterns.
