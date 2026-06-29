# ADR-002: Modular Monolith and Design Patterns

- **Estado:** Aceptado
- **Fecha:** 2026-02-01
- **Última revisión:** 2026-06-26
- **Decidido por:** [Tu nombre]

## Context

The system has a domain-heavy workflow:

- doctor eligibility and availability,
- monthly scheduling,
- fairness and explanations,
- mission ranking,
- Telegram natural language access,
- WhatsApp notifications,
- legacy imports,
- reports,
- security,
- and auditability.

The expected MVP usage is low to moderate and institutional, not high-volume commercial traffic.

The project is also intended to work as a professional portfolio project, so the implementation should be clear, testable, and maintainable without unnecessary infrastructure complexity.

## Decision

Use a modular monolith with lightweight Clean Architecture boundaries.

Backend stack:

- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Pydantic
- Railway Cron with database-backed jobs

Frontend stack:

- React
- Vite
- TanStack Query or equivalent server-state management
- Feature-based folders

Primary backend modules:

- `accounts`
- `doctors`
- `availability`
- `scheduling`
- `missions`
- `notifications`
- `telegram`
- `reports`
- `imports`
- `audit`

Primary backend layers:

- `api`: FastAPI routers, request/response schemas, dependency wiring
- `application`: use cases and orchestration
- `domain`: entities, value objects, rule contracts, scoring concepts
- `infrastructure`: database, external providers, file/export generation, cron adapters

## Design Patterns

Use these patterns where they reduce domain complexity:

- Use Case / Application Service pattern for operational flows.
- Repository pattern for persistence access.
- Strategy pattern for fairness and scoring rules.
- Specification pattern for eligibility checks.
- Scoring pipeline for candidate ranking and assignment rationale.
- Outbox/database-backed job pattern for notifications and scheduled work.
- Append-only audit log for critical actions.
- Tool-calling gateway for Telegram assistant behavior.
- Lightweight CQRS separation between commands and read/report queries.

## Non-Decisions

Do not introduce microservices for MVP.

Do not introduce Celery/Redis from day one unless workload requires it.

Do not use RAG as the authority for structured operational data.

Do not put scheduling decisions in the frontend.

Do not let the LLM decide assignments, eligibility, ranking, or final truth.

## Consequences

Benefits:

- lower operational cost,
- faster MVP delivery,
- strong separation of domain rules from framework code,
- easier testing of scheduling and mission logic,
- clearer portfolio story,
- and an evolution path toward queues/workers if needed.

Tradeoffs:

- module boundaries must be enforced by code organization and review discipline,
- long-running tasks must be carefully designed around database-backed jobs,
- and shared database access requires clear repository ownership.

## Evolution Path

Introduce Redis/Celery only when:

- imports become long-running,
- calendar generation exceeds acceptable request/cron windows,
- notification volume grows,
- operators need real-time progress for long tasks,
- or multiple task types need concurrent queue priorities.

Split services only if the monolith becomes operationally constrained after real usage data supports the change.
