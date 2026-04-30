# Spec 08 - Despliegue y Operacion Railway/Vercel

## Goal

Define the deployment and runtime strategy for a low-usage institutional scheduling system using Railway for backend services and Vercel for the frontend.

The system should minimize idle cost while preserving reliability for Telegram queries, scheduled draft generation, WhatsApp notifications, and audit-sensitive operations.

## Deployment Targets

### Vercel

Frontend:

- React + Vite application.
- Public web panel for operators and approvers.
- Calls the backend API hosted on Railway.

### Railway

Backend and data services:

- FastAPI API service.
- PostgreSQL database.
- Railway Cron service for scheduled tasks.
- Redis/Celery only when operational volume requires continuous background processing.

## MVP Runtime Strategy

The MVP should avoid always-on background workers unless they become necessary.

Recommended MVP services:

1. `api`
   - FastAPI backend.
   - Railway Serverless/App Sleeping enabled when compatible.
   - Wakes on frontend requests, Telegram webhooks, and external API calls.

2. `postgres`
   - Canonical data store.
   - Stores doctors, calendars, staged imports, notifications, audit events, scheduled tasks, and job execution logs.

3. `cron-runner`
   - Railway Cron service.
   - Starts on schedule, executes due tasks, records results, closes resources, and exits.

Deferred services:

- `redis`
- `celery-worker`
- `celery-beat`

These should be introduced only when the system needs high-frequency asynchronous processing, long-running queues, or continuous event consumption.

## Railway Cron vs Celery/Redis

Railway Cron is not a full replacement for Celery and Redis.

Railway Cron is best for:

- scheduled jobs,
- periodic checks,
- daily or monthly automation,
- short-lived tasks that can start, run, persist results, and exit.

Celery + Redis is best for:

- continuous background workers,
- high-volume task queues,
- near-real-time task processing,
- retries with queue semantics,
- long-running asynchronous processing,
- workloads where tasks must be consumed immediately after being enqueued.

For this system's MVP, Railway Cron can perform the required scheduled behavior if tasks are designed as database-backed, idempotent jobs.

## Scheduled Task Model

Scheduled work must be represented in the database.

Recommended tables or entities:

- `scheduled_job`
- `job_execution`
- `notification_event`
- `calendar_generation_request`

### ScheduledJob

Represents a pending or recurring unit of work.

Required fields:

- `id`
- `job_type`
- `status`
- `run_after`
- `locked_at`
- `locked_by`
- `attempt_count`
- `max_attempts`
- `idempotency_key`
- `payload`
- `last_error`
- `created_at`
- `updated_at`

Status values:

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `dead_letter`

### JobExecution

Represents one execution attempt.

Required fields:

- `id`
- `scheduled_job_id`
- `started_at`
- `finished_at`
- `status`
- `worker_name`
- `error_code`
- `error_message`
- `metadata`

## Cron Runner Responsibilities

The Railway Cron runner should:

1. Start on a configured schedule.
2. Open database connection.
3. Find due jobs where `run_after <= now`.
4. Lock jobs transactionally.
5. Execute jobs idempotently.
6. Persist results and audit events.
7. Release or finalize jobs.
8. Close database connections.
9. Exit cleanly.

It must not stay alive waiting for work.

## Recommended Cron Frequencies

All Railway cron schedules are evaluated in UTC. Dominican Republic local time is UTC-4.

Recommended MVP schedules:

- Notification dispatcher: every 15 minutes.
- Failed notification retry sweep: every 30 minutes.
- Calendar draft generation check: daily.
- Monthly auto-draft creation: configured day of month, initial value day 27.
- Missing availability reminder to encargado: two days before the configured monthly auto-draft day.
- Cleanup and consistency checks: daily.

Railway Cron should not be used when a task requires minute-perfect execution. For WhatsApp reminders, the product should tolerate a small execution window.

## WhatsApp Reminder Reliability

Reminder delivery should not depend on an in-memory scheduler.

The system must persist reminder jobs in the database.

Flow:

1. Calendar becomes `official`.
2. System creates notification records for initial messages.
3. System creates reminder records with `run_after = service_start_at - 12h`.
4. Cron runner periodically scans due notification records.
5. Each send uses an idempotency key.
6. Provider response is persisted.
7. Failed transient attempts are retried until `max_attempts`.
8. Permanent failures become visible in operations reports.

This design allows reminders to survive API sleep, service restarts, and cron runner restarts.

## Telegram Behavior

Telegram should use webhooks pointed at the FastAPI API.

Behavior:

- Incoming Telegram webhook wakes the API service if it is sleeping.
- API processes the query synchronously when possible.
- If a query requires heavy work, API creates a scheduled job and returns a controlled response.
- Telegram answers must remain grounded in internal tools and canonical data.
- Telegram requests must validate linked user, active account, mandatory password change status, and role permissions.
- Assistant tools may use request-scope cache and short TTL cache according to `09-asistente-operacional-tools.md`.

Potential tradeoff:

- First request after sleep may have cold-start latency.

## Cache Runtime Strategy

MVP cache should stay simple and avoid extra always-on infrastructure unless usage requires it.

Recommended MVP cache:

- request-scope cache inside one API request or Telegram interaction,
- in-process short TTL cache for stable catalogs,
- invalidation on doctor, availability, license, restriction, calendar, assignment, rule, or user permission changes.

Redis should be introduced only if multiple API instances, higher traffic, or cross-process cache coordination become necessary.

Security and permission checks must not rely on stale long-lived cache.

## Calendar Draft Generation

Automatic generation should create draft or preview calendars only.

Flow:

1. Cron runner checks whether a configured planning date has arrived.
2. Two days before the configured planning date, it checks for missing required doctor availability and creates encargado reminder notifications.
3. If next month's draft does not exist on the configured planning date, it creates a `calendar_generation_request`.
4. Generation runs with hard validations and fairness scoring.
5. Result is stored as `draft` or `preview`.
6. Encargado receives a notification or sees pending review in the panel.
7. Calendar does not become `official` without encargado approval.

## Cost Control

Recommended controls:

- Enable Railway Serverless/App Sleeping for the API when compatible.
- Keep cron jobs short-lived.
- Avoid always-on Celery workers in MVP.
- Use private networking between Railway services where possible.
- Set Railway usage alerts and a hard usage limit appropriate for the workspace.
- Keep replica counts at one for MVP.
- Monitor one week of real usage before estimating monthly cost.

## When To Introduce Redis/Celery

Introduce Redis/Celery if at least one of these becomes true:

- Imports are large and need background processing immediately after upload.
- Calendar generation takes long enough to exceed comfortable request/cron execution windows.
- Notification volume increases significantly.
- Operators require real-time progress updates for long tasks.
- Multiple task types must run concurrently with queue priorities.
- Cron polling creates unacceptable delay.

When introduced, Celery should use Redis as broker and keep scheduled task state mirrored in PostgreSQL for auditability.

## Failure Handling

Scheduled tasks must be safe under retries.

Rules:

- Every job must have an idempotency key.
- Notification sends must have provider-level and application-level idempotency.
- Job locks must expire or be recoverable.
- Partial failures must be recorded.
- Every critical scheduled action must create audit events.
- Dead-lettered jobs must be visible in operations reports.

## Acceptance Criteria

1. Given a low-usage deployment, when no user or webhook traffic exists, then the API can sleep without losing scheduled tasks.
2. Given a WhatsApp reminder, when the API is asleep, then the persisted reminder remains due and can be sent by the next cron-runner execution.
3. Given a cron-runner execution failure, when the next execution starts, then pending jobs are retried according to status, lock, and attempt policy.
4. Given automatic monthly generation, when the configured planning date arrives, then a draft or preview calendar is created without making it official.
5. Given the MVP deployment, when background processing needs grow, then the architecture defines when to add Redis and Celery.
