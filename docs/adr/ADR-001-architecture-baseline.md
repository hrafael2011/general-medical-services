# ADR-001: Architecture Baseline

- **Status:** Accepted
- **Date:** 2026-01-15
- **Last revised:** 2026-06-26
- **Decided by:** Hendrick Rafael

## Context

The system must support:

- Institutional medical shift scheduling with strict domain rules
- Operator workflows via web panel and natural language Telegram
- Automated WhatsApp notifications
- Traceability, reports, and audit of all actions
- Cost-aware operation and anti-hallucination behavior in the bot

The technology stack choice must balance MVP development speed, the ability to model complex domain rules, and future scalability.

## Decision

| Component | Choice | Alternative considered |
|-----------|--------|----------------------|
| Backend | **FastAPI** (Python) | Django REST |
| Database | **PostgreSQL** | MongoDB |
| Background jobs | **APScheduler + DB-backed jobs** | Celery + Redis (MVP) |
| Optimization | **Greedy Scoring** | OR-Tools CP-SAT (see ADR-003) |
| Operator channel | **Telegram NL assistant** (DeepSeek) | Fixed-command bot |
| Physician channel | **WhatsApp** (Meta Cloud API) | SMS, email-only |
| Frontend | **React + Vite** (PWA-ready) | Next.js |
| Production (backend) | **Railway** | Self-hosted, AWS |
| Production (frontend) | **Vercel** | Self-hosted |
| Local development | **Docker Compose** | Manual |

## Alternatives considered

### Django REST (discarded)

The domain requires async operations (WhatsApp/Telegram webhooks, external API calls). Django REST + Channels adds complexity to achieve what FastAPI provides natively. For a portfolio project with heavy external integrations, FastAPI offers better API documentation (native OpenAPI) and performance.

### Celery + Redis (discarded for MVP)

The current notification load (tens per day, not thousands) does not justify the operational overhead of maintaining Redis + Celery workers. APScheduler with PostgreSQL-backed jobs fulfills the purpose with zero additional infrastructure. Left as a documented evolution path for when scale requires it.

## Consequences

- **Positive:** Fast iteration with clear API contracts (auto-generated OpenAPI)
- **Positive:** Good fit for scheduling logic with complex domain rules
- **Positive:** Controlled LLM cost through strict tool grounding
- **Positive:** MVP with zero always-on infrastructure cost (short-lived jobs)
- **Negative:** Requires robust guardrails and fallback policy (especially in the Telegram bot)

## Follow-up Decisions

- `ADR-002-modular-monolith-design-patterns.md` defines the modular monolith implementation style and design patterns.
- `ADR-003-greedy-scoring-vs-or-tools.md` documents the scheduling algorithm decision.
