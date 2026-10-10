# Tasks — Licencias con fechas y recordatorio de reintegro

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-licencias-con-fechas-y-recordatorio.md](2026-10-09-licencias-con-fechas-y-recordatorio.md)

**Goal:** Registrar la ausencia de un médico —**eje 2, "fuera de servicio"**— con fecha de inicio
y de regreso (o **indefinido**), y avisar por Telegram y campana **X días antes** del reintegro.

> **"Inhabilitado" son ocho ejes independientes** (sistema, servicio, misiones, pool,
> restricciones, disponibilidad, áreas, borrado). Esta spec trabaja **solo el eje 2**; los otros
> siguen igual. La Fase 0 corrige los dos defectos que la investigación destapó.

**Architecture:** Se reutiliza `doctor_restrictions`, que ya tiene `starts_at` / `ends_at` y que el
motor de asignación **ya respeta** — así el médico queda fuera **solo en ese rango** y vuelve solo.
Una pantalla nueva en la ficha del médico unifica las dos representaciones de "no disponible"
(la restricción con fechas y el flag `service_active` sin fecha) para que el encargado no tenga que
saber que son dos cosas. El recordatorio es un job más del scheduler, con la idempotencia que ya
existe en `notification_events`: la clave incluye la fecha de regreso, así que **editar la fecha
re-arma el aviso sin columna nueva**.

**Tech Stack:** FastAPI, SQLAlchemy, React + TanStack Query, scheduler del proyecto, pytest, vitest

**Estado:** 🔴 **Pendiente.** Depende de [reparar el canal de Telegram](2026-10-09-reparar-canal-avisos-telegram-tasks.md):
sin canal, el aviso no llega a nadie.

---

## Fase 0 — Correcciones previas (antes de construir encima)

> Estas dos correcciones salieron de investigar **los ocho ejes** de inhabilitación. Sin ellas, la
> función nueva se apoyaría en una base que ya está inconsistente.

### Task 0.1 — Unificar las dos puertas de desactivación

**Archivos:** `backend/app/application/doctors/service.py` (`deactivate_service` ≈ línea 491 y
`update` ≈ línea 296)

Hoy hay **dos caminos** para lo mismo y dejan resultados distintos:

| | Botón "Desactivar" | Editar el médico |
|---|---|---|
| Motivo | ✅ | ❌ |
| Quita de misiones | ✅ | ❌ |
| Auditoría | `doctor_service_deactivated` | `doctor_updated` |

Eso explica los datos reales de producción: **2 médicos sin motivo** y **2 fuera de servicio pero
todavía en misiones**.

- [ ] **Decidir** cuál es el comportamiento correcto (propuesta: el de la puerta A, que es el más
      completo).
- [ ] **Hacer que `update`**, cuando recibe `service_active=False`, exija y guarde motivo y
      sincronice misiones.
- [ ] **Unificar el evento de auditoría** para que el historial no dependa de por dónde se entró.
- [ ] **Revisar los datos existentes**: los 2 sin motivo y los 2 en misiones fuera de servicio.

### Task 0.2 — Que el motivo diga si espera regreso

**Archivos:** `backend/app/infrastructure/db/models/catalogs.py` (o `doctors.py`),
migración nueva, `backend/app/domain/catalogs.py`

- [ ] **Añadir** al catálogo de motivos un campo del tipo `expects_return` (booleano).
- [ ] **Migración** que lo agregue y **clasifique los 8 motivos de producción**:
      *con regreso* → LICENCIAS MEDICAS, LICENCIA PRE Y POST NATAL, VACACIONES,
      PRESTADO BATALLAS DE LAS CARRERAS; *sin regreso* → DIRECCION, GERENCIAS MEDICAS;
      *a decidir* → CONCURSO, OTROS.
- [ ] **Exponerlo** en la API del catálogo.

> ⚠️ Es la **única migración** de esta spec. Si prefieres no migrar, se recorta: la pantalla
> siempre pregunta y el encargado elige. Pierde comodidad, no funcionalidad.

### Task 0.3 — Confirmar la clasificación con el usuario

- [ ] **Validar** la clasificación de los 8 motivos: **es criterio de negocio, no de código**.
      En particular: ¿CONCURSO y OTROS esperan regreso?

---

## Fase 1 — Fechas en la ausencia (backend)

### Task 1.1 — Confirmar la API existente

**Archivo:** `backend/app/api/routes/availability.py` (líneas 133-183)

- [ ] **Revisar** los contratos actuales de `POST /doctors/{id}/restrictions`,
      `GET /doctors/{id}/restrictions` y `POST /restrictions/{id}/lift`.
- [ ] **Verificar** que `ends_at` admite nulo y qué significa hoy en la elegibilidad
      (`eligibility.py:79`).
- [ ] **Comprobar** que `restriction_type` y `severity` se ajustan a "licencia" (`hard_block`).

> El endpoint **ya existe**: esta tarea es de reconocimiento, no de construcción. Si el contrato
> ya sirve, no se toca la ruta.

### Task 1.2 — Que el motivo sea el del catálogo

- [ ] **Confirmar** que la restricción usa `reason_id` → el **mismo** catálogo de 9 motivos que ya
      usa la desactivación (licencia médica, embarazo, vacaciones, préstamo…).
- [ ] **Rechazar** motivos que no apliquen al sexo del médico, como ya hace `deactivate_service`.

### Task 1.3 — Indefinido

- [ ] **Definir** "indefinido" como `ends_at = NULL` y **documentarlo** en el contrato.
- [ ] **Comprobar** que una restricción con `ends_at` nulo **bloquea desde `starts_at` sin fecha
      de fin** (comportamiento actual del motor) y que **no** entra en el recordatorio.

---

## Fase 2 — Los días de aviso (configuración)

### Task 2.1 — Clave en `system_settings`

- [ ] **Sembrar** `notifications.license_reminder_days` con valor **2**, reutilizando el patrón de
      `CatalogService.seed_initial_catalogs` y el `GET` con fallback que ya existe para las firmas.
- [ ] **Exponerlo** en la pestaña de configuración correspondiente para que sea editable sin
      tocar la base.

> **Sin migración**: es una fila de `system_settings`, no una columna nueva. El valor por registro
> queda fuera a propósito (ver la nota del spec).

---

## Fase 3 — El recordatorio (backend)

### Task 3.1 — El job

**Archivo:** `backend/app/application/scheduler/jobs.py` (añadir un quinto job)

- [ ] **Buscar** restricciones con `ends_at` **no nulo**, no levantadas (`lifted_at IS NULL`), cuya
      fecha de regreso caiga dentro de la ventana `hoy + N días`.
- [ ] **No** incluir las indefinidas ni las ya vencidas.
- [ ] **Crear la alerta en la campana** (`ActionAlertService.create_if_missing`) con:
      nombre del médico, motivo y fecha de reintegro, y `action_url` a la ficha del médico.
- [ ] **Encolar el aviso por Telegram** a los usuarios con Telegram vinculado y el permiso
      correspondiente, con el **mismo patrón** que `check_unconfirmed_escalamiento`
      (mensaje consolidado por destinatario).

### Task 3.2 — Idempotencia y re-armado

- [ ] **Usar** una clave de idempotencia que incluya **el id de la restricción y la fecha de
      regreso**: `license_expiring:{restriction_id}:{ends_at}`.
- [ ] **Verificar** que: la misma fecha avisa **una sola vez**; cambiar la fecha **vuelve a
      permitir** el aviso; volver a la fecha anterior **no** re-avisa.

> Es el punto delicado del spec (AC5 y AC6). La clave única de `notification_events` ya lo
> resuelve, pero hay que probarlo en los tres escenarios.

### Task 3.3 — Registrar el job

- [ ] **Añadirlo** a `_TASKS` en `run_once.py` para que el worker lo ejecute en su cron.
- [ ] **Comprobar** que es idempotente: correrlo dos veces seguidas no duplica nada.

---

## Fase 4 — La pantalla (frontend)

### Task 4.1 — Sección "No disponible" en la ficha del médico

**Archivo:** `frontend/src/features/doctors/` (lista y ficha del médico)

- [ ] **Listar** lo vigente y lo programado, unificando las dos fuentes:
      - ausencia **con fechas** (restricción) → *"Licencia médica: 1 → 15 de marzo"*
      - ausencia **sin fecha** (el flag actual) → *"Desactivado: sin fecha de regreso"*
- [ ] **Distinguir visualmente** lo que está vigente de lo que está programado a futuro.
- [ ] **Mostrar** la fecha de reintegro de forma destacada, porque es el dato que se busca.

### Task 4.2 — El formulario

- [ ] **Pedir**: motivo (catálogo), **desde**, **hasta** y la opción **Indefinido**.
- [ ] **Deshabilitar** "hasta" cuando se marca Indefinido, y explicar que en ese caso no habrá
      recordatorio.
- [ ] **Permitir editar** una ausencia existente y **levantarla** (`/lift`).
- [ ] **Validar** desde ≤ hasta antes de enviar.

### Task 4.3 — Cliente de API

**Archivo:** `frontend/src/api/doctors.ts`

- [ ] **Añadir** las funciones de listar, crear, editar y levantar restricciones (los endpoints ya
      existen; hoy el frontend no los llama).

---

## Fase 5 — Tests

- [ ] **Elegibilidad**: dentro del rango se rechaza; fuera del rango se permite **sin intervención**
      (AC2).
- [ ] **Indefinido**: bloquea desde la fecha y **nunca** genera aviso (AC3).
- [ ] **Ventana**: avisa dentro de los N días, no antes ni después (AC4).
- [ ] **Idempotencia**: dos corridas del job, un solo aviso (AC5).
- [ ] **Re-armado**: cambiar la fecha vuelve a avisar (AC6).
- [ ] **No regresión**: los médicos desactivados sin fecha siguen igual (AC7).
- [ ] **Frontend**: la sección lista ambos tipos; el formulario respeta Indefinido.

---

## Fase 6 — Verificación en vivo

- [ ] **Registrar** una licencia que empiece en el futuro y comprobar que el médico **sigue
      asignable** antes de esa fecha.
- [ ] **Intentar asignarlo** dentro del rango y comprobar el rechazo.
- [ ] **Provocar** un aviso (fecha de regreso dentro de la ventana) y confirmar que **llega** por
      Telegram y aparece en la campana.
- [ ] **Editar** la fecha y confirmar que vuelve a avisar.
- [ ] **Confirmar** que una ausencia **Indefinida** no genera nada.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué resuelve | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 0 | Fase 0 | Unificar puertas + motivo con regreso | **Medio** — toca datos y trae la única migración | ⬜ pendiente |
| 🔴 1 | Fase 1 | Fechas e indefinido en la API | Bajo — el mecanismo ya existe | ⬜ pendiente |
| 🟠 2 | Fase 2 | Los días de aviso | Bajo | ⬜ pendiente |
| 🟠 3 | Fase 3 | El recordatorio | **Medio** — idempotencia y re-armado | ⬜ pendiente |
| 🟠 4 | Fase 4 | La pantalla | Medio — unifica dos representaciones | ⬜ pendiente |
| 🟡 5 | Fase 5 | Cobertura | Bajo | ⬜ pendiente |
| 🟡 6 | Fase 6 | Verificación en vivo | Bajo | ⬜ pendiente |

## Archivos a tocar

| Archivo | Tipo |
|---|---|
| `backend/app/application/doctors/service.py` | corregir — unificar las dos puertas |
| `backend/app/infrastructure/db/models/doctors.py` | añadir — `expects_return` en el motivo |
| `migrations/versions/` | **nueva** — la única migración de esta spec |
| `backend/app/api/routes/availability.py` | revisar — probablemente sin cambios |
| `backend/app/application/availability/service.py` | revisar/ajustar — `add_restriction` |
| `backend/app/application/scheduler/jobs.py` | añadir — el job de recordatorio |
| `backend/app/application/scheduler/run_once.py` | añadir — registrarlo |
| `backend/app/application/notifications/templates.py` | añadir — plantilla del aviso |
| `backend/app/application/notifications/triggers.py` | añadir — encolar a encargados |
| `backend/app/application/catalogs/service.py` | añadir — la clave de configuración |
| `frontend/src/features/doctors/` | añadir — sección y formulario |
| `frontend/src/api/doctors.ts` | añadir — funciones de restricciones |
| Tests backend y frontend | añadir |

**Sin migraciones de esquema.**

## Casillas abiertas

1. **Depende del canal de Telegram** — si el canal sigue roto, la campana funciona pero el aviso
   por Telegram no llega.
2. **Los días de aviso son globales**, no por registro (decisión 7). Si necesitas plazos distintos
   por caso, es una columna nueva + migración, en otro cambio.
3. **Los desactivados actuales** se quedan como están (decisión 9), pero la Fase 0 propone revisar
   los 2 sin motivo y los 2 que siguen en misiones fuera de servicio.
4. **La clasificación de los 8 motivos** (Task 0.3) es criterio de negocio: falta tu confirmación
   para CONCURSO y OTROS.
5. **La única migración** de esta spec es la del campo `expects_return` (decisión 11). Se puede
   recortar si prefieres no migrar.
4. **Nada implementado todavía.**

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas. Decisiones confirmadas: fuera solo en el rango, aviso por ambos canales, indefinido entre las opciones, editar re-arma, los desactivados no se tocan, solo Telegram, **2 días de aviso por defecto**. |
| 2026-10-09 | Investigación | Se descubren **8 ejes** de inhabilitación, el catálogo real de 8 motivos (todos `hard_block`) y el estado de los 73 médicos. Se añaden la Fase 0 (unificar puertas + `expects_return`) y los requisitos R11-R15. |
