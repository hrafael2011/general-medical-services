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

### Regla de oro: `master` no se toca sin autorización escrita

`master` es **la rama de producción**: Railway (API y worker) y Vercel despliegan desde ella.
Cualquier cosa que se escriba ahí sale publicada. Por eso:

- **NUNCA** hacer `commit`, `merge` ni `push` sobre `master` sin la **autorización escrita** del
  usuario en la conversación. Vale para los tres, no solo para el push: un commit en `master`
  local ya es tocar la rama.
- Pedirla **antes** de hacerlo, diciendo exactamente qué se va a tocar (qué archivos, qué
  commits, qué comando) y esperar la respuesta. Una autorización anterior **no** sirve para
  otra cosa: es por operación.
- Si la respuesta no llega, **no se hace**. No hay autorización por defecto ni por silencio.
- **Un `push` a `master` despliega a producción.** Decirlo al pedir la autorización.

### Rama de trabajo: `development`

- **Todo el trabajo va en `development`**: commits, pruebas y pushes a `origin/development`.
- Nunca trabajar directamente en `master` (ni en `main`, `production` ni `release/*`).
- `development` es la única rama de trabajo del repositorio, además de `master`. No crear ramas
  nuevas sin pedirlo.
- Cuando algo tenga que llegar a producción, se pide autorización y, con ella, se lleva a
  `master` (merge de `development` → `master`, o el commit concreto que corresponda).

### Otras ramas protegidas: `main`, `production`, `release/*`

Para ellas rige lo mismo que para `master`: no se tocan sin autorización escrita del usuario.

