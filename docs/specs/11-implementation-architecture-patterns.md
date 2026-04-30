# Spec 11 - Implementation Architecture and Patterns

## Goal

Define the implementation architecture, internal module boundaries, and design patterns for building the medical scheduling system.

This spec complements `ADR-002-modular-monolith-design-patterns.md`.

## Architecture Style

The system is implemented as a modular monolith.

The backend uses lightweight Clean Architecture boundaries:

- `api`
- `application`
- `domain`
- `infrastructure`

Rules:

- Domain rules must not depend on FastAPI, SQLAlchemy sessions, Twilio, Telegram, DeepSeek, or filesystem details.
- Use cases orchestrate domain rules, repositories, external providers, audit, and jobs.
- Infrastructure implements persistence, providers, file generation, imports, and cron adapters.
- API routers should remain thin.

## Backend Module Boundaries

Initial modules:

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

Each module should own its:

- domain concepts,
- use cases,
- repository interfaces,
- infrastructure adapters,
- API routes when applicable,
- tests.

Cross-module calls should happen through use cases, query services, repositories, or explicit interfaces rather than arbitrary imports into another module's internals.

## Recommended Backend Structure

Conceptual layout:

```text
backend/
  app/
    api/
      routers/
      dependencies/
      schemas/
    application/
      accounts/
      doctors/
      availability/
      scheduling/
      missions/
      notifications/
      telegram/
      reports/
      imports/
      audit/
    domain/
      scheduling/
      missions/
      doctors/
      rules/
      shared/
    infrastructure/
      db/
      repositories/
      providers/
      jobs/
      exports/
      imports/
    core/
      config.py
      security.py
      time.py
      errors.py
```

The final structure may vary, but it must preserve the same separation of responsibilities.

## Use Cases

Use cases represent operational workflows.

Examples:

- `CreateEncargadoUser`
- `ResetEncargadoPassword`
- `ImportLegacyWorkbook`
- `GenerateMonthlyCalendar`
- `ApproveCalendar`
- `ReplaceCalendarAssignment`
- `GenerateMissionRanking`
- `RecommendMissionCandidates`
- `ConfirmMissionAssignment`
- `SendDueNotifications`
- `HandleTelegramMessage`
- `GenerateOperationalReport`

Rules:

- Use cases accept validated input DTOs.
- Use cases return structured results.
- Use cases create audit events for critical actions.
- Use cases must be testable without HTTP.

## Repository Pattern

Repositories isolate persistence access.

Examples:

- `DoctorRepository`
- `AvailabilityRepository`
- `CalendarRepository`
- `MissionRepository`
- `NotificationRepository`
- `AuditRepository`
- `UserRepository`

Rules:

- Domain and application code should not scatter raw SQLAlchemy queries.
- Complex read/report queries may use dedicated query services.
- Repositories must not call external APIs.

## Rule Strategy Pattern

Fairness and eligibility rules should be implemented as strategies.

Examples:

- `InactiveDoctorRule`
- `AllowedServiceAreaRule`
- `AvailabilityRule`
- `MonthlyLimitRule`
- `StrongServiceSpacingRule`
- `MissionSpacingRule`
- `AreaRotationRule`
- `LimitedAvailabilityPriorityRule`
- `FlexibilityPreservationRule`

Each rule should return structured evaluation data:

- result,
- severity,
- score delta,
- reasons,
- warnings,
- blockers.

## Specification Pattern

Eligibility checks should be composable specifications.

Examples:

- doctor is active for service,
- doctor has no active hard block,
- doctor has allowed area,
- doctor is available on date,
- doctor participates in missions,
- doctor is not already occupied.

Specifications may be used by calendar generation, mission recommendation, manual validation, and Telegram tools.

## Scoring Pipeline

Calendar and mission recommendations use a scoring pipeline:

```text
candidates
  -> hard filters
  -> soft rule evaluation
  -> score calculation
  -> tie-breakers
  -> structured rationale
```

Calendar assignment order:

1. `emergencia`
2. `pista`
3. `disponible`

The generator should:

- consider monthly load and previous 60-day load,
- solve constrained days/areas first,
- prioritize limited availability and fixed patterns,
- preserve flexible doctors when useful,
- try multiple combinations before unresolved gaps,
- and store rationale for panel and Telegram explanations.

Mission ranking should:

- include all eligible mission doctors,
- rank lower load first,
- lower priority for doctors who already performed a mission that month,
- and store ranking entries for audit.

## Commands and Queries

Use lightweight CQRS separation:

- commands mutate state and produce audit events,
- queries return read models, summaries, reports, and Telegram tool results.

Do not create separate services or databases for CQRS in MVP.

## Jobs and Outbox

Scheduled and external delivery work must be database-backed.

Use tables/entities such as:

- `scheduled_job`
- `job_execution`
- `notification_event`

Rules:

- Cron runner processes due jobs and exits.
- Jobs must be idempotent.
- Notification sends must persist provider metadata.
- Mission confirmation creates notification jobs for participants and encargado.
- Calendar approval creates initial service notification jobs.
- Reminder jobs are persisted, not kept in memory.

## Telegram Tool Gateway

Telegram assistant requests must go through a gateway:

```text
Telegram webhook
  -> account/link validation
  -> intent detection
  -> entity extraction
  -> tool authorization
  -> use case/query
  -> structured result
  -> Spanish response
```

Rules:

- The LLM cannot query the database directly.
- The LLM cannot invent data.
- The only MVP Telegram write action is confirmed mission assignment.
- All other operational mutations stay in the panel.

## Frontend Architecture

The frontend uses React + Vite with feature-based organization.

Recommended feature folders:

- `features/auth`
- `features/doctors`
- `features/availability`
- `features/calendar`
- `features/missions`
- `features/reports`
- `features/settings`
- `features/audit`

Frontend rules:

- The frontend must not implement scheduling decisions.
- The frontend displays backend validation, rationale, warnings, and conflicts.
- Operational screens should be dense, clear, and optimized for repeated work.
- Calendar assignment details should expose a "Ver razon" action or equivalent dialog.
- Forms must reflect role permissions and mandatory password change state.

## Database Guidance

Use PostgreSQL relational modeling for canonical data.

Recommended:

- UUID primary keys,
- timezone-aware timestamps,
- foreign keys and constraints,
- indexes on doctor, date, calendar version, status, and notification due dates,
- JSONB only for snapshots, metadata, structured rationale, provider payloads, and audit details where flexibility is useful.

## Testing Expectations

High-value tests:

- eligibility specifications,
- fairness strategies,
- calendar generation scenarios,
- mission ranking and confirmation,
- Telegram tool authorization and fallbacks,
- password reset and mandatory password change,
- import staging/conflict behavior,
- notification idempotency,
- audit event creation.

Acceptance scenarios from specs should become integration or use-case tests.

## Acceptance Criteria

1. Given a calendar generation use case, when tested without HTTP, then it can generate assignments, warnings, gaps, and rationale using repository/test doubles.
2. Given a Telegram mission request, when date and count are present, then the gateway calls a tool/use case rather than allowing the LLM to decide candidates.
3. Given a notification-triggering action, when provider delivery fails, then the job remains auditable and retryable without duplicate sends.
4. Given a frontend calendar assignment, when the user opens "Ver razon", then the UI displays backend-provided structured rationale.
5. Given a rule change, when a new strategy is added, then existing use cases can evaluate it without rewriting API routers.
6. Given a critical command, when it succeeds or fails, then audit behavior is explicit and testable.
