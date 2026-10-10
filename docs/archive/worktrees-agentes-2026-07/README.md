# Restos de los worktrees de agentes (julio 2026)

Estos archivos **no son código del proyecto**: son los cambios que quedaron **sin commitear** en
siete worktrees de agentes (`worktree-agent-*`) que se eliminaron el 2026-10-10 al dejar el
repositorio con solo `development` y `master`.

Se archivaron **antes** de borrar los worktrees porque había trabajo real dentro, no solo basura:
las ediciones sin commitear tocaban `cp_model.py`, `engine.py`, `scoring.py`, `generation_service.py`
y `doctors/service.py`, y había dos archivos **que nunca llegaron a master**:

- `backend/app/infrastructure/db/models/substitution.py`
- `backend/app/infrastructure/repositories/substitution.py`

(el modelo y el repositorio de **substituciones** de médicos: alguien empezó esa función y no la
terminó. Los otros archivos nuevos de esos worktrees —`objective_weights.py` y
`cleanup_orphan_availability.py`— sí están ya en master, así que sus copias aquí son solo
referencia.)

## Contenido

Un directorio por worktree:

- `cambios.patch` — los cambios sobre los archivos que ya existían, tal cual quedaron.
  Se aplica con `git apply cambios.patch` **sobre un checkout del commit `b2f17e9`**
  (el 8 de julio de 2026), que es de donde salieron los worktrees. Sobre master **no** aplica:
  han pasado 115 commits.
- `nuevos/` — copia literal de los archivos que estaban sin seguimiento (solo los de código;
  ni `.venv` ni `node_modules`).

## Si alguien quiere retomar la función de substituciones

No hace falta este archivo para nada más. El punto de partida es
`agent-a1ed62aaeba904670/nuevos/backend/app/infrastructure/…/substitution.py`, pero está
escrito contra el esquema de julio: hay que revisarlo antes de usarlo.

Este directorio se puede borrar cuando se confirme que no interesa.
