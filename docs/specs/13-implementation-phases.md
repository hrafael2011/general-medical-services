# Spec 13 - Implementation Phases

## Goal

Define the implementation roadmap in small, manageable phases.

The objective is to build the MVP incrementally without overwhelming each step, while keeping the system testable and aligned with the specs.

## Phase 0 - Scaffold and Technical Base

Goal:

- Create the project foundation.

Tasks:

- Create backend FastAPI structure.
- Create frontend React + Vite structure.
- Add local environment configuration.
- Add initial Docker Compose for local services when needed.
- Add PostgreSQL configuration.
- Add Alembic setup.
- Add baseline lint/format/test tooling.
- Add `scripts/test.sh`.
- Add backend health endpoint.
- Add frontend smoke page.
- Add initial CI workflow updates if needed.

Exit criteria:

- Backend starts locally.
- Frontend starts locally.
- Database connection works.
- Baseline tests run through the test script.

## Phase 1 - Auth, Users, and Security

Goal:

- Implement secure access for `admin` and `encargado`.

Tasks:

- Create user model and migrations.
- Implement password hashing.
- Implement login/session or token strategy.
- Implement role checks.
- Implement `must_change_password`.
- Implement admin creates encargado.
- Implement admin resets encargado password.
- Implement CLI admin password reset.
- Implement session invalidation after reset.
- Implement failed login throttling/lockout.
- Add panel login and mandatory password change screen.

Exit criteria:

- Admin can create encargado.
- Encargado must change temporary password before using the system.
- Admin can reset encargado password.
- Admin password can be reset by CLI.

## Phase 2 - Base Catalogs

Goal:

- Implement catalogs needed by doctors and scheduling.

Tasks:

- Create service areas.
- Seed MVP service areas: `emergencia`, `pista`, `disponible`.
- Create ranks.
- Create departments.
- Create deactivation reasons.
- Seed initial deactivation reasons.
- Create system configuration for calendar generation day.
- Add catalog management screens where needed.

Exit criteria:

- Required catalogs exist and can be used by later phases.
- Deactivation reasons are configurable.
- Pregnancy option is constrained to female doctors.

## Phase 3 - Doctors and Availability

Goal:

- Implement doctor master data and eligibility inputs.

Tasks:

- Create doctor CRUD.
- Add sex, rank, department, phone, notes.
- Add `participa_misiones`.
- Add service active/inactive status and reason.
- Add allowed service areas per doctor.
- Add monthly service target and maximum per doctor.
- Add monthly service limit mode.
- Add fixed weekly availability.
- Add recurring monthly availability patterns.
- Add monthly variable availability.
- Enforce fixed or monthly availability mode for MVP.
- Add restrictions/licenses entry.
- Add pending availability view.
- Add WhatsApp contact fields for future notifications.

Exit criteria:

- Encargado can configure who can serve, where, and when.
- Encargado can configure how many services each doctor should normally perform per month.
- Missing monthly availability is detectable.
- Inactive/block reasons exclude doctors from candidates.

## Phase 4 - Audit Base

Goal:

- Make critical actions traceable early.

Tasks:

- Create append-only audit event model.
- Add audit service/use case.
- Add audit creation to users, doctors, availability, restrictions, and catalogs.
- Add audit query endpoint.
- Add audit screen with filters.

Exit criteria:

- Critical changes create audit events.
- Audit can be filtered by actor, date, action, and entity.

## Phase 5 - Manual Calendar and Visualization

Goal:

- Allow the encargado to manage calendars manually before automation is complete.

Tasks:

- Create calendar and calendar version models.
- Create calendar assignment model.
- Create monthly calendar view.
- Show required daily slots.
- Allow manual assignment/replacement.
- Validate hard blocks and soft warnings.
- Require justification for soft-rule overrides.
- Store assignment rationale placeholder.
- Add "Ver razon" action in UI.
- Create official calendar approval flow.
- Create new version when official calendar is modified.

Exit criteria:

- Encargado can create, review, edit, approve, and version calendars manually.

## Phase 6 - Calendar Generation Engine

Goal:

- Generate valid monthly draft/preview calendars.

Tasks:

- Implement eligibility specifications.
- Implement fairness strategy contract.
- Implement hard filters.
- Implement soft scoring.
- Implement area assignment order: emergencia, pista, disponible.
- Implement monthly and 60-day load calculations.
- Implement monthly service target and maximum scoring.
- Implement spacing rules.
- Implement area rotation.
- Implement limited availability priority.
- Implement flexibility preservation.
- Implement constrained-day ordering.
- Implement multiple-combination attempts.
- Implement unresolved gaps.
- Store structured assignment rationale.
- Generate draft/preview only.

Exit criteria:

- System can generate a monthly draft/preview with assignments, warnings, gaps, and rationale.

## Phase 7 - Missions

Goal:

- Implement mission ranking, recommendation, and confirmation.

Tasks:

- Create mission assignment model.
- Create mission participant model.
- Create monthly mission ranking model.
- Generate ranking during calendar generation.
- Rank all eligible mission doctors with position 1 as lowest load.
- Exclude `participa_misiones = false`.
- Lower priority for doctors who already had mission that month.
- Recommend candidates by date and count.
- Skip occupied doctors in primary proposals.
- Allow alternate candidates with warnings.
- Confirm mission from panel.
- Prepare use case for Telegram-confirmed mission.
- Store mission rationale.
- Update workload after mission.

Exit criteria:

- Encargado can review mission ranking and confirm mission participants.
- Mission assignments affect future recommendations.

## Phase 8 - Notifications and Jobs

Goal:

- Implement reliable scheduled work and WhatsApp notifications.

Tasks:

- Create scheduled job model.
- Create job execution model.
- Create notification event model.
- Implement cron runner.
- Implement job locking and retry.
- Implement idempotency keys.
- Implement Twilio provider adapter with fake test provider.
- Send service assignment notifications after official calendar.
- Send 12-hour service reminders.
- Send missing availability reminder two days before generation day.
- Send mission participant notifications after mission confirmation.
- Send mission summary notification to encargado.

Exit criteria:

- Notifications are persisted, retryable, auditable, and idempotent.

## Phase 9 - Telegram Assistant

Goal:

- Implement natural language operational access through Telegram tools.

Tasks:

- Implement Telegram webhook.
- Implement Telegram user linking.
- Implement account/role/password-change validation.
- Implement LLM provider abstraction.
- Implement intent detection and entity extraction.
- Implement tool gateway.
- Implement query/report tools.
- Implement explanation tools using stored rationale.
- Implement mission candidate request by date and count.
- Implement mission confirmation two-step flow.
- Implement no-data, out-of-domain, unauthorized, and provider-failure fallbacks.
- Log Telegram interactions.

Exit criteria:

- Encargado can consult, request reports, ask explanations, request mission candidates, and confirm missions through Telegram.

## Phase 10 - Legacy Import and Reports/Exports

Goal:

- Import legacy data and produce institutional outputs.

Tasks:

- Implement source file registration.
- Ignore Office lock files.
- Implement Excel extraction.
- Implement PDF extraction/staging fallback.
- Implement checksum/versioning.
- Implement raw extraction storage.
- Implement field classification and normalization.
- Implement identity resolution.
- Implement staging review workflow.
- Apply approved staged records transactionally.
- Import historical data from January 2026 onward.
- Prefer Excel over PDF on conflicts.
- Generate calendar PDF.
- Generate operational reports.
- Generate Excel exports.
- Support Telegram report/export delivery.

Exit criteria:

- Legacy data can be staged, reviewed, applied, and used for reports and scheduling history.
- Reports and exports are available through panel and Telegram.

## Cross-Phase Rules

- Keep changes small and phase-focused.
- Add tests as defined in `12-testing-implementation-methodology.md`.
- Update specs before behavior changes.
- Preserve audit expectations for critical actions.
- Keep user-facing text in Spanish and developer-facing code/docs in English.
- Do not introduce Redis/Celery, microservices, or RAG-first behavior unless a later decision changes the architecture.

## Acceptance Criteria

1. Given the implementation starts, when Phase 0 is complete, then backend, frontend, database, and test script are operational.
2. Given each phase completes, when its exit criteria are checked, then the next phase can start without unresolved foundational blockers.
3. Given a phase introduces critical business behavior, when implementation is complete, then corresponding tests from Spec 12 exist.
4. Given the MVP reaches Phase 10, then the system supports secure operation, doctor management, scheduling, missions, notifications, Telegram, imports, and reports.
