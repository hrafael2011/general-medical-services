## Model Routing

Al usar la herramienta Agent, pasar siempre `model` según la tarea:

| model | DeepSeek real | Precio input | Precio output | Usar para |
|-------|---------------|-------------|--------------|-----------|
| `opus` | `deepseek-v4-pro` | $0.435/M | $0.87/M | Arquitectura, diseño, debugging complejo, refactors grandes, lógica pesada, SQL |
| `sonnet` | `deepseek-v4-flash` | $0.14/M | $0.28/M | Desarrollo estándar, features moderadas |
| `haiku` | `deepseek-v4-flash` | $0.14/M | $0.28/M | Boilerplate, CRUD, scaffolding, typos, búsquedas, tareas mecánicas |

> `deepseek-chat` se retira el 2026-07-24. Usar `deepseek-v4-flash` directamente.

Los agentes de exploración (`subagent_type: "Explore"`) siempre con `haiku`.

## Branch Protection

- NUNCA trabajar directamente en `main`, `master`, o `production`
- NUNCA hacer merge a `main`, `master`, o `production` sin permiso explícito
- NUNCA hacer push a `main`, `master`, o `production` sin permiso explícito
- SIEMPRE crear una feature branch antes de cualquier cambio: `git checkout -b <nombre>`
- Si el usuario pide explícitamente trabajar en rama protegida, confirmar antes de proceder

### Protected branches: `main`, `master`, `production`, `release/*`
