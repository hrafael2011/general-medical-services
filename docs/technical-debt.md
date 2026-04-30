# Technical Debt Register

This document tracks intentional technical debt, post-MVP hardening items, and future improvements.

Technical debt here is not forgotten work. It is explicitly accepted, prioritized, and revisited after the MVP is functional.

## Priority Levels

- `P0`: Must not be left unresolved if it risks security, data integrity, or core operation.
- `P1`: Important post-MVP hardening.
- `P2`: Evolution based on real usage.
- `P3`: Portfolio polish and presentation improvements.

## Entry Template

```text
ID:
Title:
Priority:
Area:
Description:
Why accepted now:
Risk:
Resolution criteria:
Related phase:
Status:
```

## P0 - Must Not Be Left Unsafe

### TD-001 - Secure Password Storage

Priority: `P0`

Area: `accounts`

Description:

- Passwords must be stored only as secure hashes using Argon2 or bcrypt.
- Plaintext passwords must never be logged or persisted.

Why accepted now:

- This is not acceptable as unresolved debt; it is tracked to ensure it remains non-negotiable during implementation.

Risk:

- Account compromise and institutional data exposure.

Resolution criteria:

- Password hashing is implemented, tested, and used by all password flows.

Related phase: `1`

Status: `open`

### TD-002 - Critical Audit Coverage

Priority: `P0`

Area: `audit`

Description:

- Critical actions must create append-only audit events.

Why accepted now:

- Must be verified continuously as features are added.

Risk:

- Loss of institutional traceability.

Resolution criteria:

- Tests prove audit events for user management, doctor changes, calendar changes, mission confirmation, imports, notifications, and Telegram critical actions.

Related phase: `4`

Status: `open`

### TD-003 - Notification Idempotency

Priority: `P0`

Area: `notifications`

Description:

- WhatsApp notifications and scheduled jobs must not send duplicates under retries.

Why accepted now:

- Tracked as a non-negotiable reliability requirement for implementation.

Risk:

- Duplicate messages to doctors or encargado, operational confusion, and provider cost.

Resolution criteria:

- Idempotency keys and retry tests cover service notifications, reminders, availability reminders, and mission notifications.

Related phase: `8`

Status: `open`

### TD-004 - Telegram Authorization and Grounding

Priority: `P0`

Area: `telegram`

Description:

- Telegram must only serve linked active users with completed password change.
- Responses must be grounded in internal tools.
- LLM must not invent operational data.

Why accepted now:

- Tracked to prevent assistant flexibility from bypassing security or data truth.

Risk:

- Data leakage, hallucinated decisions, or unauthorized access.

Resolution criteria:

- Tests cover linked user validation, role checks, no-data fallback, out-of-domain fallback, and tool-only responses.

Related phase: `9`

Status: `open`

### TD-005 - Database Migration Reproducibility

Priority: `P0`

Area: `database`

Description:

- Migrations must be reproducible from an empty database.

Why accepted now:

- Tracked as a release safety requirement.

Risk:

- Broken deploys or inconsistent environments.

Resolution criteria:

- CI or local test command can create a fresh database and apply all migrations.

Related phase: `0`

Status: `open`

## P1 - Post-MVP Hardening

### TD-101 - Evaluate OR-Tools Optimization

Priority: `P1`

Area: `scheduling`

Description:

- MVP starts with greedy + scoring. OR-Tools CP-SAT may improve global optimization.

Why accepted now:

- Greedy + scoring is simpler and faster to deliver.

Risk:

- Difficult months may require more manual changes.

Resolution criteria:

- Evaluate after real data. Add OR-Tools if manual corrections exceed an agreed threshold or if generation quality is not acceptable.

Related phase: `6`

Status: `open`

### TD-102 - Improve PDF Import Reliability

Priority: `P1`

Area: `imports`

Description:

- PDF parsing is expected to be less reliable than Excel parsing.

Why accepted now:

- Excel has priority and PDF can start as review-heavy staging.

Risk:

- Historical assignments in PDF-only files may require manual review.

Resolution criteria:

- Measure parser confidence and review volume after initial import. Improve parser or require manual templates if needed.

Related phase: `10`

Status: `open`

### TD-103 - Production Observability

Priority: `P1`

Area: `operations`

Description:

- Add structured logs, request IDs, job execution visibility, and operational error reporting.

Why accepted now:

- Basic logs are enough for early MVP, but production support needs better visibility.

Risk:

- Harder debugging after deployment.

Resolution criteria:

- Logs include request/job IDs, errors are searchable, failed jobs are visible, and provider failures are traceable.

Related phase: `8`

Status: `open`

### TD-104 - Database Index Review With Real Data

Priority: `P1`

Area: `database`

Description:

- Initial indexes should be reviewed after importing real 2026 data.

Why accepted now:

- Premature indexing without query patterns can add noise.

Risk:

- Slow reports, Telegram queries, or generation.

Resolution criteria:

- Analyze common queries and add indexes for doctor/date/calendar/status/report paths.

Related phase: `10`

Status: `open`

### TD-105 - Cache Tuning

Priority: `P1`

Area: `performance`

Description:

- MVP can use request-scope and short TTL in-process cache. Redis is deferred.

Why accepted now:

- Expected low usage does not justify extra infrastructure at first.

Risk:

- Repeated queries may become slow as data grows.

Resolution criteria:

- Add metrics or profiling. Introduce Redis only if multiple instances or real traffic requires cross-process caching.

Related phase: `9`

Status: `open`

### TD-106 - Broaden E2E Coverage

Priority: `P1`

Area: `testing`

Description:

- MVP E2E should cover critical flows first. Broader regression coverage can follow.

Why accepted now:

- Too many E2E tests early can slow iteration.

Risk:

- UI regressions in less common paths.

Resolution criteria:

- Add E2E for full monthly workflow, mission confirmation, imports review, report download, and Telegram simulated flows.

Related phase: `12`

Status: `open`

### TD-107 - Deployment Runbook

Priority: `P1`

Area: `operations`

Description:

- Create a practical runbook for Railway/Vercel deployment, environment variables, backups, cron, and incident handling.

Why accepted now:

- Specs describe architecture, but operators need a concise procedure.

Risk:

- Deployment or recovery depends on memory.

Resolution criteria:

- Runbook exists and has been followed at least once in a dry run or real deployment.

Related phase: `8`

Status: `open`

### TD-108 - Stabilize ASGI Integration Test Client

Priority: `P1`

Area: `testing`

Description:

- The initial Phase 0 backend smoke test avoids the synchronous FastAPI/Starlette test client because it hung in the local sandbox with the current dependency combination.
- API tests need a stable ASGI client strategy before heavier endpoint coverage begins.

Why accepted now:

- Phase 0 only needs a basic health smoke and route registration check.

Risk:

- API tests may be weaker until the integration test client is standardized.

Resolution criteria:

- Select and verify a reliable client pattern for FastAPI integration tests, then update API tests to exercise real ASGI requests without hanging.

Related phase: `1`

Status: `open`

## P2 - Evolution Based on Usage

### TD-201 - Redis and Celery Introduction

Priority: `P2`

Area: `jobs`

Description:

- Introduce Redis/Celery only if cron and database-backed jobs become insufficient.

Why accepted now:

- MVP workload does not justify always-on workers.

Risk:

- Long-running or high-volume jobs may become slow.

Resolution criteria:

- Add Redis/Celery if imports, generation, notifications, or concurrent jobs exceed acceptable runtime.

Related phase: `8`

Status: `open`

### TD-202 - RAG for Institutional Documents

Priority: `P2`

Area: `telegram`

Description:

- Add RAG only for documents, manuals, or policies not represented in structured data.

Why accepted now:

- Structured database remains the operational truth.

Risk:

- Some document-based questions may not be answerable initially.

Resolution criteria:

- Introduce RAG with citations and strict separation from structured operational decisions.

Related phase: `9`

Status: `open`

### TD-203 - Doctor WhatsApp Confirmation Flow

Priority: `P2`

Area: `notifications`

Description:

- Doctors could confirm receipt or availability through WhatsApp in a future version.

Why accepted now:

- MVP sends notifications but does not require doctor interaction.

Risk:

- Encargado may still need manual follow-up.

Resolution criteria:

- Add inbound WhatsApp handling only if operational process requires it.

Related phase: `8`

Status: `open`

### TD-204 - More Telegram Write Actions

Priority: `P2`

Area: `telegram`

Description:

- MVP only allows confirmed mission assignment as a Telegram write action.

Why accepted now:

- Keeping regular service/calendar changes in the panel reduces risk.

Risk:

- Some operations may require panel access even when Telegram would be faster.

Resolution criteria:

- Add more Telegram write tools only with role checks, two-step confirmation, audit, and clear UX.

Related phase: `9`

Status: `open`

### TD-205 - Advanced Analytics Dashboards

Priority: `P2`

Area: `reports`

Description:

- Add deeper dashboards for workload trends, fairness drift, service distribution, and mission history.

Why accepted now:

- Initial reports are enough for MVP operation.

Risk:

- Less insight into long-term trends.

Resolution criteria:

- Add after the basic reporting workflow is validated by real users.

Related phase: `10`

Status: `open`

### TD-206 - Multi-Institution Support

Priority: `P2`

Area: `architecture`

Description:

- Support multiple institutions or tenant-like separation in a future version.

Why accepted now:

- MVP targets one institutional workflow.

Risk:

- Expansion would require schema and authorization changes.

Resolution criteria:

- Only design after a real requirement appears.

Related phase: `future`

Status: `open`

## P3 - Portfolio Polish

### TD-301 - Public Project README

Priority: `P3`

Area: `portfolio`

Description:

- Create a polished README with problem statement, architecture, screenshots, setup, and demo flow.

Why accepted now:

- Better after implementation has real screens.

Risk:

- Project is less presentable before polish.

Resolution criteria:

- README clearly explains domain, architecture, setup, tests, and demo.

Related phase: `post-MVP`

Status: `open`

### TD-302 - Demo Data and Anonymization

Priority: `P3`

Area: `portfolio`

Description:

- Provide safe demo data that does not expose real personal or institutional information.

Why accepted now:

- Real data import comes later and must remain protected.

Risk:

- Portfolio demo cannot be shared safely without anonymization.

Resolution criteria:

- Demo seed data exists and real data is excluded from public presentation.

Related phase: `post-MVP`

Status: `open`

### TD-303 - Architecture Diagram

Priority: `P3`

Area: `portfolio`

Description:

- Add a visual architecture diagram for backend, frontend, jobs, Telegram, WhatsApp, and database.

Why accepted now:

- More useful after implementation structure exists.

Risk:

- Architecture is harder to communicate quickly.

Resolution criteria:

- Diagram included in docs or README.

Related phase: `post-MVP`

Status: `open`

### TD-304 - Demo Script or Video

Priority: `P3`

Area: `portfolio`

Description:

- Prepare a short demo script or video showing login, doctor setup, generation, mission ranking, Telegram report, and audit.

Why accepted now:

- Requires working product flows.

Risk:

- Portfolio impact is lower without a guided walkthrough.

Resolution criteria:

- Demo script or video exists and uses safe demo data.

Related phase: `post-MVP`

Status: `open`
