# Tasks — Reparar el canal de avisos por Telegram

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-reparar-canal-avisos-telegram.md](2026-10-09-reparar-canal-avisos-telegram.md)

**Goal:** Que los avisos por Telegram salgan de verdad y que, cuando no puedan salir, se vea.

**Architecture:** El canal se compone de tres piezas que hoy están desconectadas: un **proveedor**
(token del bot), un **destinatario** (vínculo del usuario o del médico) y una **cola** que
procesa. Se arreglan las tres, y se añade un cuarto: que el fallo de cualquiera de ellas deje
rastro visible en la campana en vez de morir en silencio.

**Tech Stack:** FastAPI, SQLAlchemy, Telegram Bot API, scheduler del proyecto, pytest

**Estado:** 🔴 **Pendiente — requiere autorización.** Depende de configuración en Railway
(secreto del bot), que hay que decidir y colocar a mano.

---

## Fase 0 — Decisiones previas (bloquean el resto)

### Task 0.1 — Qué bot notifica

- [ ] **Decidir** entre dos caminos:
      **(a)** crear el bot de notificaciones (`@TurnosMedicosBot`) y su token; o
      **(b)** permitir que el proveedor caiga al token del bot conversacional cuando el de
      notificaciones no exista.
- [ ] **Anotar** la decisión: afecta a los `chat_id` ya vinculados (cada bot tiene los suyos).

> El código hoy **exige** `telegram_notification_bot_token` (`providers.py:96-98`). La opción (b)
> es un cambio pequeño y permite reutilizar el bot que ya funciona; la (a) es más limpia pero
> implica crear y operar un segundo bot.

### Task 0.2 — Verificar el webhook

- [ ] **Comprobar** si el webhook del bot de notificaciones está registrado en Telegram.
      Sin él, el vínculo del médico es imposible aunque el token exista.

---

## Fase 1 — Que el vínculo de usuario llegue al job

**El bug de raíz:** el job lee `users.telegram_chat_id` y **nadie escribe ese campo**; el vínculo
vive en `telegram_user_links`.

### Task 1.1 — Unificar el destino del vínculo

**Archivos:** `backend/app/api/routes/telegram.py` (`create_link`, ≈ línea 303),
`backend/app/application/telegram/orchestrator.py` (≈ línea 864)

- [ ] **Elegir** el arreglo: **(a)** que al crear el vínculo se escriba también
      `users.telegram_chat_id`, o **(b)** que el job lea de `telegram_user_links`.
- [ ] **Implementarlo** en **los dos** puntos que crean vínculos (endpoint manual y flujo del
      bot), no en uno solo.
- [ ] **Cubrir** el caso de desvincular: al desactivar el vínculo, el campo debe quedar limpio.

> **(a) es más simple** y no toca el job; **(b) es más correcto** si un usuario pudiera tener
> varios vínculos. Decidir antes de implementar.

### Task 1.2 — Test del vínculo

- [ ] **Test**: vincular un usuario y comprobar que el job de escalación **lo encuentra**.
- [ ] **Test**: desvincular y comprobar que deja de encontrarlo.

---

## Fase 2 — Que el médico pueda vincularse

- [ ] **Confirmar** que con el token de la Fase 0 el webhook del bot de notificaciones responde.
- [ ] **Probar** el flujo real: un médico envía su teléfono, confirma, y
      `doctors.telegram_chat_id` queda escrito.
- [ ] **Documentar** el procedimiento para que el encargado pueda guiar a los médicos.

> Esta fase es sobre todo **verificación y operación**: el código del flujo ya existe
> (`telegram_notification_webhook.py:97`). Lo que falta es que el bot exista.

---

## Fase 3 — Que el fallo se vea

### Task 3.1 — Alerta cuando no hay destinatario

**Archivos:** `backend/app/application/notifications/triggers.py`,
`backend/app/application/notifications/service.py`

- [ ] **Detectar** el caso "sin destinatario" al encolar y **crear una acción visible** en la
      campana, en vez de encolar un evento condenado.
- [ ] **Reutilizar** el patrón que ya existe para el correo en `invitation_service.py`
      (`_alert_if_delivery_failed`), que hace justo esto.

### Task 3.2 — Alerta cuando el proveedor rechaza

- [ ] **Crear** la alerta equivalente a `email_delivery_failed` para notificaciones
      (`notification_delivery_failed`), con el motivo y el destinatario.

### Task 3.3 — Ver quién no puede recibir

- [ ] **Exponer** en la API ese dato para médicos y usuarios.
- [ ] **Mostrarlo** en la interfaz: distinguir de un vistazo quién no tiene Telegram vinculado.

---

## Fase 4 — Destrabar el atasco

### Task 4.1 — Criterio antes de tocar nada

- [ ] **Escribir** el criterio: las 92 notificaciones y 92 confirmaciones de septiembre
      **no se reenvían** (sería bombardear con avisos de hace un mes) — se **cierran** con un
      estado que las explique.
- [ ] **Confirmar** que quedan auditadas: quién, cuándo y por qué.

### Task 4.2 — Ejecutarlo

- [ ] **Script** con `--dry-run`, en la línea de `scripts/strip_view_audit_permission.py`.
- [ ] **Ejecutar** en local y verificar.
- [ ] **Ejecutar** en producción **después** de la Fase 2, y verificar que no queda ninguna
      `pending` antigua.

---

## Fase 5 — Verificación de punta a punta

- [ ] **Un envío de prueba** a un chat real: el evento queda `sent` con proveedor `telegram`.
- [ ] **Aprobar una semana** con un médico vinculado: recibe el aviso y su confirmación deja de
      estar huérfana.
- [ ] **Confirmar** que una confirmación vencida **escala** y el encargado **recibe**.
- [ ] **Confirmar** que un médico **sin** vínculo genera una alerta visible en vez de silencio.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué resuelve | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 0 | Fase 0 | Qué bot notifica | Bajo — decisión + secreto | ⬜ pendiente |
| 🔴 1 | Fase 1 | El vínculo llega al job | Bajo | ⬜ pendiente |
| 🔴 2 | Fase 2 | El médico puede vincularse | Bajo — verificación | ⬜ pendiente |
| 🟠 3 | Fase 3 | El fallo deja de ser silencioso | Bajo | ⬜ pendiente |
| 🟡 4 | Fase 4 | El atasco de un mes | Medio — toca datos | ⬜ pendiente |
| 🟡 5 | Fase 5 | Verificación real | Bajo | ⬜ pendiente |

## Archivos a tocar

| Archivo | Tipo |
|---|---|
| `backend/app/api/routes/telegram.py` | modificar — el vínculo escribe donde se lee |
| `backend/app/application/telegram/orchestrator.py` | modificar — ídem en el flujo del bot |
| `backend/app/application/notifications/triggers.py` | modificar — alerta si no hay destinatario |
| `backend/app/application/notifications/service.py` | modificar — alerta si el proveedor falla |
| `backend/app/application/scheduler/jobs.py` | modificar — leer el vínculo correcto |
| `scripts/resolve_stuck_notifications.py` | **nuevo** — el atasco, con `--dry-run` |
| Interfaz: quién no puede recibir avisos | modificar |
| Tests | añadir |

**Sin migraciones de esquema** (los campos y tablas ya existen).

## Casillas abiertas

1. **Decisión de la Fase 0** (qué bot notifica) — bloquea todo lo demás.
2. **El token** hay que crearlo/colocarlo en Railway: no lo puedo hacer sin tu autorización.
3. **Nada de esto se ha ejecutado** todavía.

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas a partir del análisis de producción. Sin implementar. |
