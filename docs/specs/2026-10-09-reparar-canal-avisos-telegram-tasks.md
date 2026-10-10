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

### Task 0.1 — Diseño de bots ✅ DECIDIDO

**Decidido por el usuario (2026-10-09):** **dos bots con roles separados.**

| Bot | Quién lo usa | Para qué |
|---|---|---|
| `@TurnosMedicosBot` (notificaciones) | **Médicos + encargados + admins** | Avisos, confirmaciones por botón, escalaciones consolidadas |
| `@MedicalSchedule_bot` (conversacional) | **Solo encargados y admins** | El asistente de consultas |

- [x] **Decidir** el diseño de bots.
**Estado real medido consultando la API de Telegram (2026-10-09):**

| Bot | Token | Estado |
|---|---|---|
| `@TurnosMedicosNotificaciones_bot` | el suyo | ✅ **vivo** — pero su webhook apunta a `…-staging-staging.up.railway.app`, que **devuelve 404** |
| `@MedicalSchedule_bot` (asistente) | el suyo | ❌ **BORRADO** — `getMe` responde `Unauthorized` |
| `TELEGRAM_BOT_TOKEN` de producción | otro distinto | ❌ **INVÁLIDO** — `Unauthorized` |

- [x] **Confirmar** que el bot de notificaciones existe y está vivo.
- [ ] **Recrear** `@MedicalSchedule_bot` (el asistente): está borrado, y el enlace de vínculo de
      usuarios apunta a él, así que hoy **es imposible vincularse**. Telegram libera el nombre al
      borrar, así que probablemente se pueda recuperar el mismo.
- [ ] **Corregir** el webhook del bot de notificaciones: hoy apunta a un entorno **borrado**.
      Debe apuntar a `https://general-medical-services-production.up.railway.app/api/webhooks/telegram-notification`
      con `secret_token` = `TELEGRAM_WEBHOOK_SECRET`.
- [ ] **Colocar** los cuatro valores en Railway, API **y** worker:
      `TELEGRAM_BOT_TOKEN` (asistente, nuevo) · `TELEGRAM_BOT_USERNAME` ·
      `TELEGRAM_NOTIFICATION_BOT_TOKEN` · `TELEGRAM_NOTIFICATION_BOT_USERNAME` (variable nueva).
- [ ] **Registrar** también el webhook del asistente: `/api/telegram/webhook`. *(cuando se recree el bot)*

> ⚠️ **Los tokens se pegaron en el chat**, así que están expuestos: **rotarlos en BotFather**
> antes de configurarlos, y que los secretos los coloque el usuario (no pasarlos por aquí).

> El asistente **ya** está restringido a staff (`_TELEGRAM_LINKABLE_ROLES`), así que este diseño
> refleja la intención que el código ya tenía. Lo que falta es que exista el bot que envía.

### Task 0.2 — Configuración nueva

- [x] **Añadir** `telegram_notification_bot_username` a `core/config.py`: hoy el deep link usa
      `telegram_bot_username` (el asistente), que es justo el bot equivocado.
- [ ] **Colocar** el token del bot de notificaciones en Railway (API **y** worker).
- [ ] **Registrar** el webhook del bot de notificaciones.

### Task 0.3 — Permiso de los avisos ✅ DECIDIDO

- [x] **Reutilizar** `receive_escalation_alerts`. Confirmado por el usuario: quien ya recibe las
      escalaciones es exactamente quien debe recibir estos avisos.

---

## Fase 0-bis — La causa raíz: los jobs reventaban ✅ HECHO

**Archivos:** `backend/app/infrastructure/db/models/__init__.py`,
`backend/app/infrastructure/db/session.py`

- [x] **Importar los 31 modelos** en `models/__init__.py` (antes: 2 de 31).
- [x] **Importar el paquete desde `session.py`**: así "poder hablar con la base" y "conocer todas
      las tablas" son lo mismo, y el worker queda cubierto por construcción.
- [x] **Test de regresión en proceso limpio** (`tests/infrastructure/test_model_registration.py`):
      comprobado que **falla sin el arreglo** y pasa con él.
- [x] **Verificar** ejecutando el worker en local: 0 tracebacks.

> Sin esto, arreglar el token no habría servido de nada: los jobs morían antes de enviar y
> reportaban ceros.

---

## Fase 1 — Que el vínculo del staff llegue al job

**El bug de raíz:** el job lee `users.telegram_chat_id` y **nadie escribe ese campo**.

**Con el diseño de dos bots, cada campo tiene un significado claro:**

| Dónde | Qué guarda | Para qué |
|---|---|---|
| `users.telegram_chat_id` | El chat del **bot de notificaciones** | **Recibir avisos** — es lo que el job lee |
| `telegram_user_links` | El vínculo con el **asistente** | Consultar por el bot conversacional |

> El campo `users.telegram_chat_id` **fue diseñado justo para esto**: el job ya lo lee. Lo que
> falta es que **algo lo escriba**. No hay que cambiar el job.

### Task 1.1 — Que el bot de notificaciones atienda `/start <token>`

**Archivo:** `backend/app/api/routes/telegram_notification_webhook.py`

- [ ] **Detectar** un `/start <token>` de un usuario del sistema (hoy ese webhook solo espera
      teléfonos de médicos y responde "escribe tu número").
- [ ] **Validar** el token contra `telegram_link_tokens` (la tabla sirve igual: token, usuario,
      caducidad; es agnóstica del bot).
- [ ] **Escribir** `users.telegram_chat_id` con el `chat_id` de **ese** bot y marcar el token
      como usado.
- [ ] **Responder** confirmando la vinculación al canal de avisos.
- [ ] **No romper** el flujo del médico: un `/start` **sin** token sigue pidiendo el teléfono.

### Task 1.2 — El enlace apunta al bot correcto

**Archivo:** `backend/app/api/routes/telegram.py` (`create_link_token`, ≈ línea 381)

- [ ] **Construir** el deep link con `telegram_notification_bot_username` (configuración nueva,
      Task 0.2) en vez de `telegram_bot_username`, que es el asistente.
- [ ] **Decidir** si hacen falta **dos** enlaces distintos (uno por bot) o uno solo al canal de
      avisos y el asistente se sigue vinculando como hoy. *(propuesta: dos botones en la
      pantalla, "Vincular a avisos" y "Vincular al asistente")*

### Task 1.3 — Tests

- [ ] **Test**: un encargado abre el enlace del canal y `users.telegram_chat_id` queda escrito.
- [ ] **Test**: el job de escalación **lo encuentra** y le encola el aviso.
- [ ] **Test**: un médico que escribe su teléfono sigue vinculándose igual (no regresión).
- [ ] **Test**: desvincular limpia el campo.

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

### Task 3.3 — El acuse al encargado (confirmado en esta spec)

**Archivo:** `backend/app/api/routes/telegram_notification_webhook.py` (≈ línea 239)

- [ ] **Quitar** el `status="skipped"` con el que nace el evento `{tipo}_confirmed`, y darle
      **destinatarios reales**: los usuarios con `receive_escalation_alerts`.
- [ ] **Verificar** que el acuse llega y que no se duplica (clave `confirmed:{id}` ya es única).

> Es un aviso que hoy **nace desactivado a propósito**. Se arregla aquí y no en el spec B
> porque es el mismo tipo de bug: un mensaje que nunca sale.

### Task 3.4 — Ver quién no puede recibir

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
| 🔴 1 | Fase 1 | El vínculo del staff llega al job | Bajo | ⬜ pendiente |
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
