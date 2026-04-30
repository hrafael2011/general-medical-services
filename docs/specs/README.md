# Spec-Driven Development Guide

This project follows a spec-driven workflow: requirements first, contracts second, code third.

## Workflow

1. Create/update a feature spec under `docs/specs/`.
2. Define acceptance criteria using Given/When/Then.
3. Define or update API contracts (FastAPI/OpenAPI).
4. Implement code in API, workers, and/or web panel.
5. Add/adjust tests for acceptance and integration.
6. Open PR using the spec checklist.

## Spec Rules

- No behavior changes without a spec update.
- No new endpoint without contract update.
- All critical actions must define audit expectations.
- Telegram NL must use tools/endpoints (no freeform data answers).
- If data is unavailable, assistant must return controlled "no data" response.

## Language Conventions

This project is also intended to serve as a professional portfolio project.

Developer-facing material should be written in English:

- code identifiers,
- code comments,
- tests,
- commits and PR descriptions,
- technical documentation,
- ADRs,
- internal tool names,
- endpoint names,
- and system/developer prompts.

End-user-facing material should be written in Spanish:

- web panel labels,
- validation and error messages,
- Telegram assistant responses,
- WhatsApp templates,
- exported reports,
- visible role labels,
- and confirmation prompts.

LLM prompts may be authored in English for maintainability, but they must explicitly instruct the model to answer end users in Spanish.

## Spec Index

- `00-proceso-manual-actual.md`
- `01-medicos-disponibilidad.md`
- `02-calendario-fairness.md`
- `03-telegram-nl-deepseek.md`
- `04-notificaciones-whatsapp.md`
- `05-reportes-auditoria.md`
- `06-modelo-dominio.md`
- `07-importacion-legacy.md`
- `08-despliegue-operacion-railway-vercel.md`
- `09-asistente-operacional-tools.md`
- `10-seguridad-acceso-usuarios.md`
- `11-implementation-architecture-patterns.md`
- `12-testing-implementation-methodology.md`
- `13-implementation-phases.md`
- `appendix-intents-v1.md`
