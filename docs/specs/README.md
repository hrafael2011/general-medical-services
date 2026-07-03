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

## Versioning Convention

Every spec file carries a YAML frontmatter block and a `## Changelog` section at the bottom.

### Frontmatter fields

```yaml
---
spec: <number>
version: <MAJOR>.<MINOR>.<PATCH>
status: draft | accepted | deprecated
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

| Field | Meaning |
|-------|---------|
| `spec` | Spec number matching the filename prefix |
| `version` | Semantic version of this spec document |
| `status` | `draft` while being discussed, `accepted` once agreed and implemented, `deprecated` when superseded |
| `created` | Date the spec was first written |
| `updated` | Date of the last changelog entry |

### Version bump rules

| Change type | Bump |
|-------------|------|
| Domain rule or acceptance criterion removed or broken | **MAJOR** |
| New domain rule, new acceptance criterion, new scope item | **MINOR** |
| Clarification, wording fix, additional example, typo | **PATCH** |

### Changelog entry format

Each entry in `## Changelog` must include:

| Column | Content |
|--------|---------|
| `Version` | The new version after this change |
| `Date` | YYYY-MM-DD |
| `Issue` | GitHub Issue number (`#123`) or `—` if none |
| `Trigger` | `Inicial` / `Bug` / `Nuevo requerimiento` / `Actualización` / `Feedback` |
| `Resumen` | One-line description of what changed and why |

### Trigger types

- **Inicial** — first version of the spec.
- **Bug** — a defect found in QA or production revealed a missing or incorrect requirement.
- **Nuevo requerimiento** — a new operational need was identified.
- **Actualización** — an existing requirement was refined, tightened, or expanded.
- **Feedback** — direct input from the coordinator or end users changed the spec.

### Rule

No spec change may be merged without a matching changelog entry. If the change links to a GitHub Issue, the issue number is mandatory in the entry. Changelog entries in a PR description are accepted as evidence when the spec file itself is updated in the same PR.

---

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

---

## Spec Index

| # | File | Version | Status | Updated |
|---|------|---------|--------|---------|
| 00 | [00-proceso-manual-actual.md](00-proceso-manual-actual.md) | 1.0.0 | accepted | 2026-04-30 |
| 01 | [01-medicos-disponibilidad.md](01-medicos-disponibilidad.md) | 1.3.0 | accepted | 2026-04-30 |
| 02 | [02-calendario-fairness.md](02-calendario-fairness.md) | 1.1.0 | accepted | 2026-04-30 |
| 03 | [03-telegram-nl-deepseek.md](03-telegram-nl-deepseek.md) | 1.0.0 | accepted | 2026-04-30 |
| 04 | [04-notificaciones-whatsapp.md](04-notificaciones-whatsapp.md) | 1.0.0 | accepted | 2026-04-30 |
| 05 | [05-reportes-auditoria.md](05-reportes-auditoria.md) | 1.0.0 | accepted | 2026-04-30 |
| 06 | [06-modelo-dominio.md](06-modelo-dominio.md) | 1.2.0 | accepted | 2026-04-30 |
| 07 | [07-importacion-legacy.md](07-importacion-legacy.md) | 1.3.0 | accepted | 2026-04-30 |
| 08 | [08-despliegue-operacion-railway-vercel.md](08-despliegue-operacion-railway-vercel.md) | 1.1.0 | accepted | 2026-04-30 |
| 09 | [09-asistente-operacional-tools.md](09-asistente-operacional-tools.md) | 1.0.0 | accepted | 2026-04-30 |
| 10 | [10-seguridad-acceso-usuarios.md](10-seguridad-acceso-usuarios.md) | 1.0.0 | accepted | 2026-04-30 |
| 11 | [11-implementation-architecture-patterns.md](11-implementation-architecture-patterns.md) | 1.1.0 | accepted | 2026-04-30 |
| 12 | [12-testing-implementation-methodology.md](12-testing-implementation-methodology.md) | 1.0.0 | accepted | 2026-04-30 |
| 13 | [13-implementation-phases.md](13-implementation-phases.md) | 1.0.0 | accepted | 2026-04-30 |
| 14 | [14-bot-conversacional-hybrido.md](14-bot-conversacional-hybrido.md) | 1.0.0 | draft | 2026-05-06 |
| 15 | [15-telegram-router-query-engine.md](15-telegram-router-query-engine.md) | 1.0.0 | draft | 2026-07-02 |
| — | [appendix-intents-v1.md](appendix-intents-v1.md) | 1.0.0 | accepted | 2026-04-30 |
