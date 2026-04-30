# Spec 03 - Telegram NL Assistant (DeepSeek)

## Goal

Provide a Telegram assistant for operational queries in natural language, with strict anti-hallucination behavior.

## Scope

- Intent detection
- Entity extraction
- Tool-calling to internal services
- Controlled response formatting
- Out-of-domain rejection
- Role and account-status validation before operational answers
- Interaction logging for audit and improvement

## Non-Goals

- No freeform autonomous decisions
- No direct database answering without service/tool
- No menu-driven interaction as primary UX
- No database of pre-written questions as the primary interaction model
- No RAG-first answering for structured operational data

## LLM Policy

- Provider: DeepSeek (configurable)
- Temperature: low for factual responses
- Response must be grounded in tool output JSON
- LLM interprets intent and entities; backend tools decide truth, eligibility, ranking, and explanations
- Recommendations and explanations must use backend-provided scores, reasons, blockers, and `data_as_of`
- System and developer prompts may be written in English for maintainability.
- User-facing Telegram responses must be written in Spanish.
- Required fallback phrases must remain in Spanish exactly as specified unless a future localization policy changes them.

## Guardrails

- Closed catalog of supported intents (see appendix).
- If no tool or data is available, respond:
  - "No tengo esa informacion en el sistema."
- If the request is outside the system scope, respond:
  - "No puedo responder eso porque esta fuera del alcance del sistema."
- If the request is unauthorized for the linked user's role, respond:
  - "No tienes permiso para consultar esa informacion."
- Out-of-domain queries must be rejected professionally.
- Sensitive/destructive actions require two-step confirmation.
- Telegram users must be linked to active system users before receiving operational data.
- Users with pending mandatory password change cannot use assistant intents.
- Prompt injection attempts must not override tool, role, fallback, or audit policies.

## Operational Tooling

The assistant behavior is governed by `09-asistente-operacional-tools.md`.

Every supported intent must map to an internal tool or endpoint with:

- required entities,
- allowed roles,
- input/output schema,
- fallback behavior,
- cache policy,
- and audit level.

The assistant may ask clarification questions when required entities are missing.

## Response Language

The assistant should understand informal Spanish, including typos and operational shorthand.

It must answer the end user in clear institutional Spanish.

Internal tool names, logs, and prompt instructions may remain in English, but raw internal naming should not leak into normal user-facing responses.

## Fallback Policy

- Timeout threshold configured per query.
- Bounded retries.
- If provider fails or tool-call invalid:
  - return controlled fallback response
  - log incident (`provider_error`, `timeout`, `invalid_tool_call`)
- If direct deterministic endpoint is available, use degraded direct path.

## Acceptance Criteria

1. Given a supported operational query, assistant returns accurate result grounded on tools.
2. Given an unsupported query, assistant rejects without hallucinating.
3. Given LLM provider outage, assistant returns controlled fallback and logs incident.
4. Given ambiguous query, assistant asks a focused clarification question.
5. Given an unauthorized or unlinked Telegram user, assistant returns no operational data and logs the event.
6. Given a recommendation query, assistant explains the result using only backend-provided rationale.
