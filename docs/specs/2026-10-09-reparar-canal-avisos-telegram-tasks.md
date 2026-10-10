# Tasks — Reparar el canal de avisos por Telegram

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-reparar-canal-avisos-telegram.md](2026-10-09-reparar-canal-avisos-telegram.md)

**Goal:** Que los avisos por Telegram salgan de verdad y que, cuando no puedan salir, se vea.

**Architecture:** El canal se compone de tres piezas que hoy están desconectadas: un **proveedor**
(token del bot), un **destinatario** (vínculo del usuario o del médico) y una **cola** que
procesa. Se arreglan las tres, y se añade un cuarto: que el fallo de cualquiera de ellas deje
rastro visible en la campana en vez de morir en silencio.

**Tech Stack:** FastAPI, SQLAlchemy, Telegram Bot API, scheduler del proyecto, pytest

**Estado:** 🟡 **Implementado y desplegado; falta la prueba con un chat real.** El código de las
Fases 0-bis → 4 está en `master` y en producción. Lo que queda (Fase 5) no es código: hace falta
que **al menos una persona vincule su Telegram** (hoy: 0 de 5 usuarios y 0 de 73 médicos), y
**recrear `@MedicalSchedule_bot`**, que sigue borrado.

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
      con `secret_token` = `TELEGRAM_WEBHOOK_SECRET`. ✅ **HECHO** — re-registrado y verificado
      con `getWebhookInfo` (2026-10-09).
- [ ] **Colocar** los cuatro valores en Railway, API **y** worker:
      `TELEGRAM_BOT_TOKEN` (asistente, nuevo) · `TELEGRAM_BOT_USERNAME` ·
      `TELEGRAM_NOTIFICATION_BOT_TOKEN` · `TELEGRAM_NOTIFICATION_BOT_USERNAME` (variable nueva).
      🟡 **A medias**: los dos del bot de **avisos** ya están colocados en Railway (API y worker,
      con `--skip-deploys`). Los dos del **asistente** no, porque ese bot está borrado.
- [ ] **Registrar** también el webhook del asistente: `/api/telegram/webhook`. *(cuando se recree el bot)*

> ⚠️ **Los tokens se pegaron en el chat**, así que están expuestos: **rotarlos en BotFather**
> antes de configurarlos, y que los secretos los coloque el usuario (no pasarlos por aquí).
> **Decisión del usuario (2026-10-09):** no rotarlos — "solo yo tengo acceso a este chat".

> El asistente **ya** está restringido a staff (`_TELEGRAM_LINKABLE_ROLES`), así que este diseño
> refleja la intención que el código ya tenía. Lo que falta es que exista el bot que envía.

### Task 0.2 — Configuración nueva

- [x] **Añadir** `telegram_notification_bot_username` a `core/config.py`: hoy el deep link usa
      `telegram_bot_username` (el asistente), que es justo el bot equivocado.
- [x] **Colocar** el token del bot de notificaciones en Railway (API **y** worker).
- [x] **Registrar** el webhook del bot de notificaciones.

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

- [x] **Detectar** un `/start <token>` de un usuario del sistema (hoy ese webhook solo espera
      teléfonos de médicos y responde "escribe tu número").
- [x] **Validar** el token contra `telegram_link_tokens` (la tabla sirve igual: token, usuario,
      caducidad; es agnóstica del bot).
- [x] **Escribir** `users.telegram_chat_id` con el `chat_id` de **ese** bot y marcar el token
      como usado.
- [x] **Responder** confirmando la vinculación al canal de avisos.
- [x] **No romper** el flujo del médico: un `/start` **sin** token sigue pidiendo el teléfono.

### Task 1.2 — El enlace apunta al bot correcto

**Archivo:** `backend/app/api/routes/telegram.py` (`create_link_token`, ≈ línea 381)

- [x] **Construir** el deep link con `telegram_notification_bot_username` (configuración nueva,
      Task 0.2) en vez de `telegram_bot_username`, que es el asistente. Si falta la variable,
      el endpoint responde **503** en vez de devolver un enlace que no sirve.
- [x] **Decidir** si hacen falta **dos** enlaces distintos (uno por bot) o uno solo al canal de
      avisos y el asistente se sigue vinculando como hoy.
      **Decidido:** el enlace que se muestra al usuario va **al bot de avisos** (es el que
      escribe el campo que el job lee). El asistente conserva su vínculo por
      `telegram_user_links` y el segundo enlace se devuelve aparte como
      `assistant_deep_link_url` *(hoy no lo usa ninguna pantalla: el bot del asistente está
      borrado, así que mostrarlo sería ofrecer un enlace muerto)*.

### Task 1.3 — Tests

**Archivo:** `backend/tests/telegram/test_notification_webhook.py` (7 tests, todos en verde)

- [x] **Test**: un encargado abre el enlace del canal y `users.telegram_chat_id` queda escrito.
- [x] **Test**: el job de escalación **lo encuentra** y le encola el aviso.
- [x] **Test**: un médico que escribe su teléfono sigue vinculándose igual (no regresión).
- [x] **Test**: token reusado, token vencido y chat ya vinculado a otra cuenta → rechazados.
- [ ] **Test**: desvincular limpia el campo. ❌ **NO HECHO — y es un hueco real, no un olvido
      de test.** `DELETE /telegram/links/{id}` solo pone `telegram_user_links.active = false`
      (es el vínculo del **asistente**), y **no** toca `users.telegram_chat_id`, que es del
      **bot de avisos**. Consecuencia: quitar un vínculo en la pantalla **no** revoca la
      recepción de avisos. Hace falta una acción explícita de "revocar canal de avisos".

---

## Fase 2 — Que el médico pueda vincularse

- [ ] **Confirmar** que con el token de la Fase 0 el webhook del bot de notificaciones responde.
      🟡 El webhook **está registrado** (`getWebhookInfo` apunta a producción con `secret_token`),
      pero aún no ha llegado ningún mensaje real: nadie ha abierto el bot.
- [ ] **Probar** el flujo real: un médico envía su teléfono, confirma, y
      `doctors.telegram_chat_id` queda escrito.
- [x] **Documentar** el procedimiento para que el encargado pueda guiar a los médicos.
      (Sección "¿Quién puede recibir avisos?" → botón **Instrucciones**, que copia el texto
      listo para reenviar por WhatsApp: abrir el bot, `/start` y el teléfono sin guiones.)

> Esta fase es sobre todo **verificación y operación**: el código del flujo ya existe
> (`telegram_notification_webhook.py:97`). Lo que falta es que el bot exista.

---

## Fase 3 — Que el fallo se vea

### Task 3.1 — Alerta cuando no hay destinatario

**Archivos:** `backend/app/application/notifications/triggers.py`,
`backend/app/application/notifications/service.py`

- [x] **Detectar** el caso "sin destinatario" al encolar y **crear una acción visible** en la
      campana, en vez de encolar un evento condenado.
      (`_create_missing_recipient_alert()` en `notifications/service.py`.)
- [x] **Reutilizar** el patrón que ya existe para el correo en `invitation_service.py`
      (`_alert_if_delivery_failed`), que hace justo esto.

### Task 3.2 — Alerta cuando el proveedor rechaza

- [x] **Crear** la alerta equivalente a `email_delivery_failed` para notificaciones
      (`notification_delivery_failed`), con el motivo y el destinatario.
      (`notifications/service.py:161`.)

### Task 3.3 — El acuse al encargado (confirmado en esta spec)

**Archivo:** `backend/app/api/routes/telegram_notification_webhook.py` (≈ línea 239)

- [x] **Quitar** el `status="skipped"` con el que nace el evento `{tipo}_confirmed`, y darle
      **destinatarios reales**: los usuarios con `receive_escalation_alerts`.
- [x] **Verificar** que el acuse llega y que no se duplica (clave `confirmed:{id}` ya es única).

> Es un aviso que hoy **nace desactivado a propósito**. Se arregla aquí y no en el spec B
> porque es el mismo tipo de bug: un mensaje que nunca sale.

### Task 3.4 — Ver quién no puede recibir

- [x] **Exponer** en la API ese dato para médicos y usuarios: `DoctorRead.has_telegram` (derivado
      de `doctors.telegram_chat_id`) y `UserRead.telegram_chat_id`. El chat id del médico **no**
      se expone: solo el booleano. Verificado contra el esquema OpenAPI que sirve la API.
- [x] **Mostrarlo** en la interfaz: sección **"¿Quién puede recibir avisos?"** en la pantalla de
      Telegram, con ✅/❌ por usuario y por médico, contador ("Usuarios: 1 de 2"), filtro
      "Ver solo los que NO reciben", "Generar link" para el usuario sin canal y
      "Instrucciones" (copiables) para el médico, que es el único que puede vincularse solo.
      Cubierto por 6 tests en `frontend/src/features/telegram/TelegramLinks.test.tsx`
      (comprobado por mutación: 3 de ellos fallan si se quita la lógica).

---

## Fase 4 — Destrabar el atasco

### Task 4.1 — Criterio antes de tocar nada

- [ ] **Escribir** el criterio: las 92 notificaciones y 92 confirmaciones de septiembre
      **no se reenvían** (sería bombardear con avisos de hace un mes) — se **cierran** con un
      estado que las explique.
- [ ] **Confirmar** que quedan auditadas: quién, cuándo y por qué.

### Task 4.2 — Ejecutarlo

- [x] **Script** con `--dry-run`, en la línea de `scripts/strip_view_audit_permission.py`.
      (`scripts/resolve_stuck_notifications.py`, con `--days`.)
- [x] **Ejecutar** en local y verificar.
- [x] **Ejecutar** en producción y verificar que no queda ninguna `pending` antigua.
      **Resultado en producción:** 92 eventos → `skipped` (`error_code="stale_never_delivered"`)
      y 92 confirmaciones → `expired`; **0 `pending`** restantes.

---

## Fase 5 — Verificación de punta a punta

> **Nada de esta fase se puede hacer todavía con datos reales:** hay **0 vínculos** (0 de 5
> usuarios y 0 de 73 médicos). Es trabajo de operación, no de código: hay que vincular al menos
> una persona. El worker ya no revienta (Fase 0-bis) y el canal está configurado, así que en
> cuanto alguien se vincule esta fase se puede cerrar.

- [ ] **Un envío de prueba** a un chat real: el evento queda `sent` con proveedor `telegram`.
- [ ] **Aprobar una semana** con un médico vinculado: recibe el aviso y su confirmación deja de
      estar huérfana.
- [ ] **Confirmar** que una confirmación vencida **escala** y el encargado **recibe**.
- [ ] **Confirmar** que un médico **sin** vínculo genera una alerta visible en vez de silencio.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué resuelve | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 0 | Fase 0 | Qué bot notifica | Bajo — decisión + secreto | 🟡 avisos listo; falta recrear el asistente |
| 🔴 1 | Fase 1 | El vínculo del staff llega al job | Bajo | ✅ hecho (falta revocar el canal) |
| 🔴 2 | Fase 2 | El médico puede vincularse | Bajo — verificación | 🟡 código listo, sin probar con un chat real |
| 🟠 3 | Fase 3 | El fallo deja de ser silencioso | Bajo | ✅ hecho |
| 🟡 4 | Fase 4 | El atasco de un mes | Medio — toca datos | ✅ hecho en producción |
| 🟡 5 | Fase 5 | Verificación real | Bajo | ⬜ bloqueada por falta de vínculos |

## Archivos a tocar

| Archivo | Tipo |
|---|---|
| `backend/app/api/routes/telegram.py` | modificar — el vínculo escribe donde se lee |
| `backend/app/application/telegram/orchestrator.py` | modificar — ídem en el flujo del bot |
| `backend/app/application/notifications/triggers.py` | modificar — alerta si no hay destinatario |
| `backend/app/application/notifications/service.py` | modificar — alerta si el proveedor falla |
| `backend/app/application/scheduler/jobs.py` | modificar — leer el vínculo correcto |
| `scripts/resolve_stuck_notifications.py` | **nuevo** — el atasco, con `--dry-run` |
| `backend/app/infrastructure/db/models/__init__.py` | modificar — los 31 modelos registrados |
| `backend/app/infrastructure/db/session.py` | modificar — importar el paquete antes del engine |
| `frontend/src/features/telegram/TelegramLinks.tsx` | modificar — "¿Quién puede recibir avisos?" |
| Tests | añadir |

**Sin migraciones de esquema** (los campos y tablas ya existen).

## Casillas abiertas

1. **Recrear `@MedicalSchedule_bot`** (el asistente): sigue borrado. No bloquea los avisos —el
   canal de avisos es otro bot y ya está vivo—, pero sin él no funciona el asistente
   conversacional ni el `assistant_deep_link_url`.
2. **Revocar el canal de avisos**: no existe forma de desvincular a alguien de la recepción de
   avisos (`DELETE /telegram/links/{id}` solo desactiva el vínculo del asistente). **Hueco
   detectado al construir la pantalla**, no arreglado para no ampliar el alcance sin permiso.
3. **Nadie está vinculado todavía**: 0 de 5 usuarios y 0 de 73 médicos. Mientras eso siga así,
   todo el canal está construido pero no entrega nada.

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas a partir del análisis de producción. Sin implementar. |
| 2026-10-09 | Fase 0-bis | Causa raíz (2 de 31 modelos) arreglada, con test de regresión en proceso limpio. |
| 2026-10-09 | Fase 1 | `/start <token>` vincula al bot de avisos; 7 tests nuevos. |
| 2026-10-09 | Fase 3 | Alerta sin destinatario, `notification_delivery_failed` y acuse al encargado. |
| 2026-10-09 | Fase 4 | Ejecutado en producción: 92 + 92 filas cerradas, 0 `pending`. |
| 2026-10-09 | Task 3.4 | Pantalla "¿Quién puede recibir avisos?" + 6 tests de interfaz. |
| 2026-10-09 | — | Desplegado a producción (`253799c`): API y worker en verde, `/api/health` 200. |
