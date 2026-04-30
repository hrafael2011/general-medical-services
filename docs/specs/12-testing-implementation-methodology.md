# Spec 12 - Testing and Implementation Methodology

## Goal

Define how automated tests are added and executed throughout implementation without slowing development unnecessarily.

The project should stay safe through incremental delivery: each phase adds the tests that match its risk.

## Principles

- Tests are added as features are implemented.
- Unit tests cover domain rules, scoring, eligibility, and pure logic.
- API/integration tests cover FastAPI endpoints, persistence, authorization, audit, and jobs.
- E2E tests cover critical user workflows only.
- LLM behavior is tested through tool routing, authorization, fallbacks, and mocked provider responses.
- External providers such as Twilio, Telegram, and DeepSeek must be faked or mocked in automated tests.
- Test commands should be scriptable so the right subset can be run without unnecessary work.

## Test Script Contract

Create a single test runner script:

```bash
./scripts/test.sh unit
./scripts/test.sh api
./scripts/test.sh e2e
./scripts/test.sh backend
./scripts/test.sh frontend
./scripts/test.sh scheduling
./scripts/test.sh telegram
./scripts/test.sh phase <number>
./scripts/test.sh all
```

Rules:

- `unit` runs fast backend/domain and frontend unit tests.
- `api` runs backend integration/API tests.
- `e2e` runs browser/user-flow tests.
- `phase <number>` runs the minimum required suite for that phase.
- `all` runs the full suite expected before major delivery.

The exact internal implementation may evolve, but these command names should remain stable once introduced.

## Phase Test Matrix

### Phase 0 - Scaffold and Technical Base

Tests:

- backend health check,
- frontend render smoke test,
- lint/check baseline.

Why:

- verifies the project can run locally and in CI.

### Phase 1 - Auth, Users, and Security

Tests:

- password hashing and verification,
- role authorization,
- `must_change_password` blocking,
- admin creates encargado,
- admin resets encargado password,
- CLI admin password reset,
- login failure throttling/lockout,
- E2E login and mandatory password change.

Why:

- security is foundational and hard to retrofit safely.

### Phase 2 - Base Catalogs

Tests:

- service areas CRUD/seed behavior,
- ranks and departments,
- deactivation reasons,
- pregnancy reason only for female doctors,
- configuration validation.

Why:

- doctors, scheduling, and reports depend on stable catalog data.

### Phase 3 - Doctors and Availability

Tests:

- doctor create/update,
- service active/inactive behavior,
- allowed service areas,
- monthly service target and maximum,
- fixed availability,
- monthly availability,
- recurring fixed patterns such as last Friday,
- missing availability exclusion,
- eligibility specifications.

Why:

- doctor eligibility is the base for scheduling and missions.

### Phase 4 - Audit Base

Tests:

- audit event creation,
- append-only behavior,
- filters by actor/date/action/entity,
- critical actions create audit records.

Why:

- traceability is a core system guarantee.

### Phase 5 - Manual Calendar and Visualization

Tests:

- create monthly calendar,
- view calendar slots,
- manual assignment,
- warnings for soft-rule conflicts,
- hard block behavior,
- assignment rationale visible through API/UI,
- E2E manual replacement with justification.

Why:

- the encargado must be able to work even before full automation.

### Phase 6 - Calendar Generation Engine

Tests:

- service area assignment order,
- hard filters,
- soft scoring,
- 60-day recent load,
- monthly service target and maximum scoring,
- spacing rules,
- area rotation,
- limited availability priority,
- flexibility preservation,
- constrained-day ordering,
- unresolved gaps,
- structured rationale,
- generated draft/preview only.

Why:

- this is the highest-risk business logic.

### Phase 7 - Missions

Tests:

- mission candidate ranking generation,
- `participa_misiones` filtering,
- lower priority after a mission in same month,
- date/count requirement,
- candidate recommendation,
- alternate candidate behavior with warnings,
- mission confirmation,
- mission load impact,
- audit creation.

Why:

- missions affect fairness and include the only MVP Telegram write action.

### Phase 8 - Notifications and Jobs

Tests:

- scheduled job locking,
- retry policy,
- idempotency keys,
- official-calendar notification jobs,
- 12-hour reminders,
- missing availability reminder,
- mission participant notifications,
- encargado mission summary notification,
- fake Twilio provider metadata.

Why:

- notifications must not be duplicated or silently lost.

### Phase 9 - Telegram Assistant

Tests:

- intent detection contract with mocked LLM output,
- entity extraction validation,
- tool authorization,
- linked user checks,
- mandatory password change blocking,
- no-data fallback,
- out-of-domain fallback,
- report/export request,
- mission candidate request,
- mission confirmation two-step flow,
- provider failure fallback.

Why:

- Telegram must stay flexible without bypassing system rules.

### Phase 10 - Legacy Import and Reports/Exports

Tests:

- Excel parser fixtures,
- PDF parser fallback/staging behavior,
- Office lock file ignore,
- source checksum/versioning,
- Excel priority over PDF conflict,
- January 2026 onward staging,
- identity resolution review cases,
- report generation,
- calendar PDF export,
- Telegram report file delivery.

Why:

- imports can contaminate canonical data, and reports are institutional outputs.

## Execution Policy

During implementation:

- run the smallest relevant suite after each focused change,
- run the phase suite before closing a phase,
- run `all` before a major handoff or deployment.
- use medium reasoning effort by default unless the task risk suggests otherwise.
- before entering a high-complexity or high-risk task, Codex must notify the user that switching to high reasoning effort is recommended.

Recommended command examples:

```bash
./scripts/test.sh unit
./scripts/test.sh api
./scripts/test.sh phase 6
./scripts/test.sh all
```

## Reasoning Escalation Guidance

Medium reasoning effort is sufficient for most implementation work.

Codex should recommend switching to high reasoning effort before working on:

- calendar generation engine,
- fairness/scoring logic,
- mission ranking logic,
- complex legacy import parsing,
- security/auth edge cases,
- audit-critical behavior,
- delicate database migrations,
- bugs that remain unclear after one or two attempts,
- or changes that affect several central modules at once.

The recommendation should happen before implementation continues on that risky block, so the user can decide whether to switch modes.

## Acceptance Criteria

1. Given a phase is implemented, when the phase is closed, then its required test subset can be run through `./scripts/test.sh phase <number>`.
2. Given a domain rule changes, when tests are updated, then affected unit tests cover the rule without requiring full E2E.
3. Given a critical user workflow changes, when tests are updated, then at least one E2E or integration test covers the workflow.
4. Given external providers are involved, when tests run, then provider calls are mocked or faked.
5. Given a major delivery is prepared, when `./scripts/test.sh all` runs, then unit, API/integration, and E2E suites are executed.
6. Given a high-risk implementation block is about to start, then Codex warns the user that high reasoning effort is recommended before continuing.
