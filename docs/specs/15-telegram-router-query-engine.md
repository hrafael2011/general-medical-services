---
spec: 15
version: 1.0.0
status: draft
created: 2026-07-02
updated: 2026-07-02
---

# Spec 15 - Telegram Routed Query Engine

## Goal

Refactor the Telegram conversational assistant into a routed query engine that is faster,
safer, and more predictable without introducing LlamaIndex as a central dependency in the
first implementation.

The assistant must route each user message before invoking expensive or risky logic. It
must answer simple conversational messages cheaply, resolve operational questions through
existing deterministic services and semantic layers first, use the SQL Agent only as a
controlled fallback, generate reports through validated Pydantic contracts, and reject
unsupported or unauthorized requests without hallucinating.

## Status

This spec is a draft implementation target. It supersedes the earlier generic proposal to
replace the bot with a LlamaIndex-based RouterQueryEngine as the immediate path.

LlamaIndex remains a possible future adapter, but it is not part of this initial
implementation because the repository already contains working equivalents for several
required responsibilities:

- `backend/app/application/telegram/intent_router.py`
- `backend/app/application/telegram/tool_registry.py`
- `backend/app/application/telegram/semantic_layer/`
- `backend/app/application/telegram/sql_agent/`
- `backend/app/application/telegram/doctor_query_service.py`
- `backend/app/application/telegram/calendar_query_service.py`
- `backend/app/application/telegram/orchestrator.py`
- `backend/app/application/telegram/agent.py`

## Context

The current Telegram assistant already has meaningful separation between the webhook,
orchestrator, agent, semantic layer, deterministic services, memory, SQL Agent, and
Telegram Bot API client.

The remaining operational problems are not best solved by replacing the whole stack at
once. The main issues are:

- trivial messages may still enter a heavier LLM path than necessary,
- routing can select the wrong operational domain,
- SQL fallback can be reached too early,
- report generation requires stricter validated contracts,
- webhook processing may remain exposed to long-running LLM or report operations,
- observability is insufficient for knowing why a response was produced,
- unsupported requests must be rejected consistently instead of answered from model
  memory.

## Scope

This spec covers:

- a lightweight Telegram message router,
- chitchat handling without SQL,
- operational query routing using existing internal services first,
- SQL Agent fallback restrictions,
- report request contracts using Pydantic,
- Telegram document delivery for approved reports,
- controlled fallback responses in Spanish,
- route-level observability,
- feature-flagged rollout,
- regression tests for Telegram, SQL Agent, report contracts, and notifications touched
  by Telegram.

## Non-Goals

- No LlamaIndex migration in this phase.
- No full async rewrite of the backend in this phase.
- No replacement of the existing `ConversationalAgent` unless required by tests.
- No new external vector database.
- No autonomous write operations through Telegram, except flows already allowed by
  existing accepted specs.
- No unrestricted natural language access to every database table.
- No direct LLM output passed to WeasyPrint, openpyxl, or report generation code.
- No freeform answer from model memory for operational facts.

## Relationship With Existing Specs

This spec extends and tightens:

- `03-telegram-nl-deepseek.md`
- `09-asistente-operacional-tools.md`
- `14-bot-conversacional-hybrido.md`
- `appendix-intents-v1.md`

If this spec conflicts with a previous draft plan, this spec controls the immediate
implementation path for the routed Telegram assistant.

## Core Principle

The router decides the path. The backend decides the truth. The LLM may interpret and
format, but it must not be the source of operational data.

The execution order must be:

1. validate webhook, user, feature flags, and rate limit,
2. sanitize input,
3. route the message,
4. execute the safest applicable backend path,
5. validate structured outputs,
6. present the result in Spanish,
7. log the route and outcome.

## Target Architecture

```text
Telegram Webhook
  -> Webhook Guard
     - secret token
     - feature flag
     - rate limit
     - linked active user
     - input sanitizer
  -> TelegramMessageRouter
     - chitchat
     - operational_query
     - report_request
     - clarification
     - unsupported
  -> Route Handler
     - ChitchatHandler
     - Semantic/Deterministic Query Layer
     - Report Contract Layer
     - SQL Agent Fallback
  -> Presenter
     - Spanish text response
     - Telegram document response
  -> Interaction Audit and Observability
```

## Target Components

Primary components:

- `backend/app/application/telegram/message_router.py`
- `backend/app/application/telegram/chitchat.py`
- `backend/app/application/telegram/report_contracts.py`
- `backend/app/application/telegram/agent.py`
- `backend/app/application/telegram/orchestrator.py`
- `backend/app/application/telegram/intent_router.py`
- `backend/app/application/telegram/query_executor.py`
- `backend/app/application/telegram/sql_agent/`
- `backend/app/api/routes/telegram.py`

Secondary components:

- `backend/app/application/reports/`
- `backend/app/application/notifications/`
- `backend/app/schemas/telegram.py`
- `backend/app/core/config.py`
- `backend/tests/telegram/`
- `backend/tests/reports/`
- `backend/tests/notifications/`

## Configuration

Add a feature flag:

```env
FEATURE_TELEGRAM_ROUTER=true
```

Behavior:

- `false`: keep the current assistant path.
- `true`: use the new routed path.

The flag must default to safe behavior. If the setting is absent, the implementation may
default to the current path until the routed path has enough regression coverage.

## Allowed Data Domains

The bot may answer operational questions only from approved domains:

- doctors,
- doctor availability,
- calendars,
- calendar versions,
- calendar assignments,
- calendar weeks,
- missions,
- mission assignments,
- service areas,
- departments,
- ranks,
- confirmations where role policy permits,
- notification summaries where role policy permits,
- reports generated from approved operational data.

The bot must not expose or query these domains through natural language:

- password hashes,
- password reset or set-password tokens,
- login attempts,
- JWT internals,
- internal secrets,
- raw audit payloads unless explicitly allowed by existing role policy,
- deleted-user sensitive data,
- Telegram link tokens except through admin endpoints,
- unrestricted user records,
- destructive database operations.

## Route Decision Contract

The router must return a structured decision.

```python
class TelegramRouteDecision(BaseModel):
    route: Literal[
        "chitchat",
        "operational_query",
        "report_request",
        "clarification",
        "unsupported",
    ]
    confidence: float
    reason: str
    normalized_text: str
    entities: dict[str, Any] = {}
    requested_format: Literal["text", "pdf", "excel"] | None = None
    requires_llm: bool = False
```

Rules:

- Deterministic routing must run before LLM routing.
- Chitchat must not access SQL or operational services.
- Report requests must not execute report generation until the report contract validates.
- Unsupported requests must return a controlled Spanish response.
- Low-confidence routing must ask one focused clarification question.

## Route Types

### `chitchat`

Use for:

- greetings,
- thanks,
- farewell,
- basic help,
- capability explanation,
- polite small talk that does not require operational data.

Required behavior:

- no database query,
- no SQL Agent,
- no report generation,
- no operational data leakage,
- Spanish response.

Example response:

```text
Puedo ayudarte con consultas sobre medicos, disponibilidad, calendarios, guardias,
misiones y reportes disponibles en el sistema.
```

### `operational_query`

Use for:

- doctors by rank, sex, department, service area, status, or availability,
- calendar assignments and status,
- mission rankings and assignments where allowed,
- confirmation status where allowed,
- operational counts, lists, summaries, and comparisons.

Execution priority:

1. `SemanticLayerResolver`
2. specialized services such as `DoctorQueryService` and `CalendarQueryService`
3. `IntentRouter`
4. approved registry or deterministic query path
5. SQL Agent fallback

The SQL Agent fallback must not be the first option for known operational intents.

### `report_request`

Use for:

- "genera PDF",
- "exporta a Excel",
- "descarga reporte",
- "reporte de guardias",
- "calendario en PDF",
- "listado en Excel".

Report generation must use a Pydantic contract before calling report services.

### `clarification`

Use when:

- the intent is supported but required entities are missing,
- multiple domains are equally likely,
- the requested period is ambiguous,
- a report format is missing and cannot be inferred.

The assistant must ask one focused question.

### `unsupported`

Use when:

- request is outside the system scope,
- request requires prohibited tables,
- request is destructive,
- request asks for secrets or credentials,
- request cannot be answered safely from approved data.

Required response:

```text
No puedo responder eso porque esta fuera del alcance del sistema.
```

If the topic is in scope but no data exists:

```text
No tengo esa informacion en el sistema.
```

## Chitchat Handler

Create:

```text
backend/app/application/telegram/chitchat.py
```

Responsibilities:

- detect and answer common conversational messages,
- explain capabilities without promising unrestricted database access,
- keep responses short,
- never call SQL,
- never call report generation,
- avoid LLM unless explicitly configured for ambiguous conversational text.

## Operational Query Execution

Operational queries must use the safest available path.

Preferred path:

```text
user text
  -> entity resolver
  -> semantic layer
  -> deterministic service or IntentRouter
  -> structured result
  -> Spanish presenter
```

Fallback path:

```text
user text
  -> SQL Agent fallback
  -> SQL validation
  -> read-only execution
  -> structured rows
  -> Spanish presenter
```

The fallback path exists to increase coverage, not to bypass tool policy.

## SQL Agent Policy

The SQL Agent must:

- allow only `SELECT`,
- reject `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, and DDL/DML variants,
- reject multiple statements,
- reject prohibited tables,
- cap result size,
- avoid exposing UUIDs unless required internally,
- return controlled fallback when the query cannot be validated,
- log validation result and rejection reason.

The SQL Agent must not:

- answer from model memory,
- execute SQL before validation,
- expose auth/security data,
- alter database state,
- generate reports directly.

## Report Contract Layer

Create:

```text
backend/app/application/telegram/report_contracts.py
```

Initial contract:

```python
class TelegramReportRequest(BaseModel):
    report_type: Literal[
        "calendar",
        "doctor_list",
        "workload",
        "coverage",
        "mission_ranking",
    ]
    output_format: Literal["pdf", "excel"]
    date_from: date | None = None
    date_to: date | None = None
    month: int | None = None
    year: int | None = None
    department: str | None = None
    service_area: str | None = None
    rank: str | None = None
    sex: Literal["male", "female"] | None = None
```

Validation rules:

- report type must be known,
- format must be `pdf` or `excel`,
- required period fields must be present for calendar-like reports,
- filters must be validated against catalogs or database values,
- if required data is missing, ask clarification instead of generating a file.

The LLM may help extract parameters into the contract, but the contract must validate
before report services run.

Report generation must call existing services where possible:

- `backend/app/application/reports/report_service.py`
- `backend/app/application/reports/pdf_templates.py`
- `backend/app/application/reports/weasyprint_gen.py`
- other existing report functions already covered by tests.

## Telegram Response Rules

Text response:

- user-facing text must be Spanish,
- answer only from structured backend data,
- no internal SQL or tool names unless authorized and explicitly requested,
- no UUID leakage in normal responses,
- no hallucinated doctors, assignments, dates, or counts.

Document response:

- send through `send_document`,
- include a short Spanish message,
- filename must be deterministic and safe,
- interaction must record `has_document=true`.

## Webhook Behavior

The webhook must keep the existing security posture:

- `FEATURE_TELEGRAM`,
- webhook secret validation,
- rate limiting,
- linked active user validation,
- input sanitization,
- interaction logging.

This spec recommends preparing the webhook for fast acknowledgment and background
processing, but does not require a full async/background migration in the first pass.

If background processing is introduced:

- the webhook should return `200 OK` after accepting the job,
- duplicate Telegram updates must be idempotent,
- the bot must send the eventual response using Telegram Bot API,
- errors must be sent as controlled user-facing messages where appropriate.

## Observability

Every processed Telegram message must log structured metadata:

```json
{
  "telegram_event": "route_completed",
  "telegram_user_id": "...",
  "route": "operational_query",
  "confidence": 0.93,
  "used_llm": true,
  "used_sql": false,
  "used_sql_agent": false,
  "match_type": "semantic_layer",
  "latency_ms": 1234,
  "fallback_reason": null,
  "has_document": false
}
```

Required fields:

- route selected,
- confidence,
- handler path,
- LLM used or not,
- SQL used or not,
- SQL Agent fallback used or not,
- fallback reason,
- latency,
- document generated or not.

SQL text may be logged only at DEBUG level and must not expose secrets.

## Security Requirements

- Telegram users must be linked to active system users before operational answers.
- Role policy from existing specs must continue to apply.
- Prompt injection must not override route policy, SQL policy, role policy, or fallback
  phrases.
- Destructive commands must be rejected.
- Prohibited tables must be rejected.
- Report generation must not accept unvalidated LLM strings as render input.
- Sensitive identifiers must not be shown in normal Telegram replies.
- The bot must degrade safely if DeepSeek is unavailable.

## Failure Modes

If the LLM provider fails:

```text
No pude procesar la solicitud en este momento. Intentalo nuevamente mas tarde.
```

If data is not found:

```text
No tengo esa informacion en el sistema.
```

If the request is outside scope:

```text
No puedo responder eso porque esta fuera del alcance del sistema.
```

If authorization fails:

```text
No tienes permiso para consultar esa informacion.
```

If report parameters are incomplete:

- ask one focused clarification question.

## Implementation Phases

### Phase 0 - Baseline and Inventory

Tasks:

- review current Telegram flow,
- list existing deterministic handlers,
- list supported report services,
- list allowed and prohibited tables,
- identify existing tests that must keep passing.

Exit criteria:

- implementation notes identify the exact current integration point,
- no code behavior changed.

### Phase 1 - Message Router

Tasks:

- create `message_router.py`,
- implement `TelegramRouteDecision`,
- implement deterministic route detection,
- add LLM-minimal route classification only if deterministic routing is ambiguous,
- add unit tests.

Exit criteria:

- greetings route to `chitchat`,
- report requests route to `report_request`,
- operational questions route to `operational_query`,
- unsafe or out-of-scope requests route to `unsupported`.

### Phase 2 - Chitchat Handler

Tasks:

- create `chitchat.py`,
- add fixed responses for greetings, thanks, farewell, and help,
- integrate with the agent or orchestrator under feature flag,
- prove that chitchat does not call SQL or SQL Agent.

Exit criteria:

- chitchat response returns without SQL,
- user-facing text is Spanish,
- observability records route `chitchat`.

### Phase 3 - Operational Query Routing

Tasks:

- integrate route `operational_query` with existing semantic and deterministic services,
- ensure SQL Agent fallback remains available but later in priority,
- keep existing memory behavior unless tests reveal contamination,
- add route-level fallback reasons.

Exit criteria:

- known doctor/calendar/mission queries use deterministic or semantic paths,
- fallback SQL Agent runs only when needed,
- unsupported operational queries return controlled fallback.

### Phase 4 - SQL Agent Hardening

Tasks:

- verify table allowlist and denylist,
- verify SELECT-only validation,
- cap rows,
- block multiple statements,
- add tests for prohibited tables and destructive statements.

Exit criteria:

- unsafe SQL is rejected before execution,
- prohibited tables are rejected,
- valid allowed-domain questions can still be answered.

### Phase 5 - Report Contracts

Tasks:

- create `report_contracts.py`,
- define initial `TelegramReportRequest`,
- validate report type, format, period, and filters,
- connect valid contracts to existing report services,
- send generated documents through Telegram.

Exit criteria:

- valid report requests generate PDF or Excel,
- incomplete report requests ask clarification,
- invalid report types are rejected,
- no direct LLM string reaches WeasyPrint/openpyxl as trusted structure.

### Phase 6 - Observability

Tasks:

- add structured logs for route decisions and outcomes,
- add `has_document`, `used_sql_agent`, `fallback_reason`, and `latency_ms`,
- ensure logs do not expose secrets.

Exit criteria:

- every route emits useful trace metadata,
- test suite can assert route metadata where appropriate.

### Phase 7 - Rollout

Tasks:

- add feature flag,
- keep old path available,
- document activation/deactivation,
- run regression tests,
- optionally enable in staging before production.

Exit criteria:

- flag off uses current behavior,
- flag on uses routed behavior,
- rollback does not require code revert.

## Acceptance Criteria

### Chitchat

Given a linked active Telegram user,
when the user sends `Hola, buenos dias`,
then the bot responds in Spanish through the `chitchat` route,
and no SQL query or SQL Agent call is executed.

### Help

Given a linked active Telegram user,
when the user asks `que puedes hacer`,
then the bot explains supported operational capabilities without promising unrestricted
database access.

### Operational Query

Given a linked active Telegram user,
when the user asks `Que medicos estan de guardia manana`,
then the bot routes to `operational_query`,
uses an approved semantic/deterministic path or validated SQL fallback,
and answers only from system data.

### No Data

Given a supported operational question,
when the database has no matching records,
then the bot responds:

```text
No tengo esa informacion en el sistema.
```

### Unsupported Request

Given any Telegram user,
when the user asks for information outside the system scope,
then the bot responds:

```text
No puedo responder eso porque esta fuera del alcance del sistema.
```

### Prohibited Table

Given a linked active Telegram user,
when the user asks for password tokens, login attempts, secrets, or raw auth data,
then the bot rejects the request before SQL execution.

### Destructive SQL

Given any routed SQL fallback,
when generated SQL contains `DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, or multiple
statements,
then validation rejects it before execution.

### Report PDF

Given a linked active Telegram user with permission,
when the user asks for a supported PDF report with complete required filters,
then the bot validates a `TelegramReportRequest`, generates the report through an approved
report service, and sends it with `send_document`.

### Report Excel

Given a linked active Telegram user with permission,
when the user asks for a supported Excel report with complete required filters,
then the bot validates a `TelegramReportRequest`, generates the report through an approved
report service, and sends it with `send_document`.

### Report Clarification

Given a report request with missing required period or filter,
when the route is `report_request`,
then the bot asks one focused clarification question and does not generate a file.

### Observability

Given any processed Telegram message,
when the response is completed,
then structured logs include route, confidence, handler path, LLM usage, SQL usage,
fallback reason, latency, and document status.

### Feature Flag

Given `FEATURE_TELEGRAM_ROUTER=false`,
when a Telegram message is processed,
then the existing assistant path remains active.

Given `FEATURE_TELEGRAM_ROUTER=true`,
when a Telegram message is processed,
then the routed assistant path is used.

## Test Plan

Required test groups:

```bash
./.venv/bin/python -m pytest backend/tests/telegram
./.venv/bin/python -m pytest backend/tests/reports
./.venv/bin/python -m pytest backend/tests/notifications
```

Minimum new or updated tests:

- router classifies chitchat,
- router classifies operational queries,
- router classifies report requests,
- router rejects unsupported requests,
- chitchat does not call SQL,
- deterministic operational route is preferred over SQL Agent,
- SQL Agent rejects destructive statements,
- SQL Agent rejects prohibited tables,
- report contract validates supported reports,
- incomplete report asks clarification,
- document response uses `send_document`,
- feature flag switches between old and new path,
- webhook security and rate limiter tests keep passing.

## Rollback Plan

Rollback must be possible by setting:

```env
FEATURE_TELEGRAM_ROUTER=false
```

No database migration should be required for the first implementation unless later phases
add persistent metrics or route history tables. If persistent observability is added, it
must be backward-compatible and optional.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Router misclassifies operational queries | Low-confidence clarification and regression tests |
| SQL Agent still receives too many queries | Prioritize semantic and deterministic handlers |
| Report generation becomes too generic | Limit to approved report types and Pydantic contracts |
| LLM outage affects routing | Deterministic routing first and controlled provider fallback |
| Webhook timeouts continue | Prepare background-processing seam after routed behavior stabilizes |
| Existing bot behavior regresses | Feature flag and full Telegram regression suite |
| Sensitive data leaks through SQL fallback | Table denylist, SELECT-only validation, and output sanitization |

## Future Considerations

LlamaIndex may be evaluated later for a narrow role if metrics show that the local router
or SQL Agent is insufficient.

Possible future uses:

- structured router adapter,
- Text-to-SQL adapter for a narrow allowlisted schema,
- report-parameter extraction adapter,
- semantic example retrieval.

Adoption criteria:

- lower latency or higher accuracy than the local implementation,
- no loss of security controls,
- no bypass of existing Pydantic/report contracts,
- measurable improvement in tests and staging telemetry.

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---------|------|-------|---------|---------|
| 1.0.0 | 2026-07-02 | — | Inicial | Define la especificacion SDD para migrar el bot Telegram a un motor enrutado sin introducir LlamaIndex como dependencia central inicial. |
