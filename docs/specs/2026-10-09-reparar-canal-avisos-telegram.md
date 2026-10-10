---
spec: reparar-canal-avisos-telegram
version: 1.0.0
status: draft
created: 2026-10-09
updated: 2026-10-09
---

# Spec — Reparar el canal de avisos por Telegram

## Goal

Que los avisos por Telegram **salgan de verdad**. Hoy el sistema crea filas en la base que
nunca se convierten en mensajes, y lo hace **en silencio**: cree que avisó y no avisó a nadie.

**Tareas de implementación:** [2026-10-09-reparar-canal-avisos-telegram-tasks.md](2026-10-09-reparar-canal-avisos-telegram-tasks.md)

## Contexto

Origen: al analizar el recordatorio de licencias (spec B) se descubrió que **el canal que ese
recordatorio necesita está muerto**. Construir el aviso encima habría producido una función que
dice "avisé" sin avisar — exactamente lo que ya pasa hoy.

### Evidencia medida en producción (2026-10-09)

| Medición | Resultado |
|---|---|
| Notificaciones encoladas | **92**, todas `pending`, del 9-10 de septiembre, **todas sin destinatario** |
| Confirmaciones creadas al aprobar semanas | **92**, todas `pending`, **0 escaladas** en un mes |
| Médicos con Telegram vinculado | **0 de 73** |
| Usuarios con Telegram vinculado | **0 de 5** |
| `TELEGRAM_NOTIFICATION_BOT_TOKEN` | **ausente** |
| `META_WHATSAPP_TOKEN` / `PHONE_NUMBER_ID` | **ausentes** |
| `job_executions` / `scheduled_jobs` | **0 filas** |

### 🔴 La causa raíz, encontrada al mirar los logs del worker

**Los jobs del scheduler reventaban.** Los logs de producción muestran:

```
NoReferencedTableError: 'notification_events.assignment_id' could not find table 'calendar_assignments'
Job process_notification_queue    -> {'sent': 0, 'failed': 0, 'skipped': 0}   ← REVENTÓ
Job check_unconfirmed_escalamiento -> {'escalations': 0}                      ← REVENTÓ (atrapado en silencio)
Job process_overdue_confirmations  -> {'expired': 0}                          ← REVENTÓ
```

`models/__init__.py` importaba **2 de 31** modelos, y SQLAlchemy resuelve las claves
foráneas por nombre de tabla. La API nunca lo notó porque importar las rutas arrastra todos
los modelos; **el worker no importa rutas**, así que cada job importaba solo los suyos y moría
en la primera clave foránea que apuntaba fuera.

**Y reportaba ceros**, como si no hubiera nada que enviar. Eso es lo que hizo que 184 filas
llevaran un mes atascadas sin que nadie lo notara — y significa que **el canal estaba roto por
el crash, no solo por el token ausente**: con el token puesto, tampoco habría salido nada.

**Arreglo:** `models/__init__.py` importa los 31 modelos y `session.py` importa el paquete, de
modo que "poder hablar con la base" y "conocer todas las tablas" sean lo mismo. Verificado
ejecutando el worker en local: antes 3 tracebacks, ahora ninguno.

> El test de regresión corre en un **proceso limpio**, porque en el proceso de tests el conftest
> ya importa los modelos y el test pasaría **con el bug puesto** (falso positivo comprobado).

### Las tres causas restantes, cualquiera de ellas basta

**1. Sin proveedor configurado.**
La selección de proveedor es: `TELEGRAM_NOTIFICATION_BOT_TOKEN` → Meta/WhatsApp → `FakeProvider`.
Con los tres tokens ausentes, **cae al `FakeProvider`**, que solo escribe en el log y devuelve
un id falso. El sistema marca el envío como exitoso.

**2. `users.telegram_chat_id` no lo escribe nadie.**
El job de escalación busca destinatarios con:
```python
UserModel.active.is_(True),
UserModel.telegram_chat_id.is_not(None),
UserModel.permissions.contains(["receive_escalation_alerts"]),
```
…pero en todo el código **ninguna línea asigna `users.telegram_chat_id`**. El vínculo real se
guarda en `telegram_user_links` (endpoint manual `POST /api/telegram/links`, y el flujo del bot
en `orchestrator.py:864`). **Consecuencia: aunque un encargado vincule su Telegram, el aviso
sigue sin llegarle.** La función es inalcanzable por construcción.

**3. Los médicos no pueden vincularse.**
Quien vincula a un médico es `@TurnosMedicosBot`, es decir **el bot de notificaciones**
(`telegram_notification_webhook.py:97` escribe `doctor.telegram_chat_id`). Sin
`TELEGRAM_NOTIFICATION_BOT_TOKEN` ese bot no existe en producción ⇒ **el vínculo es imposible**.
Por eso 0 de 73 están vinculados. Y el bot conversacional (`TELEGRAM_BOT_TOKEN`, que sí está
configurado) es **otro bot**, con otro `chat_id`, y su token no sirve para notificar.

**4. El único destinatario posible es Telegram.**
`_resolve_recipient_phone()` devuelve **solo** `telegram_chat_id`; nunca cae al WhatsApp del
médico, aunque lo tenga. Decisión del usuario: **Telegram es el único canal por ahora**, así que
esto no se cambia — pero hace que el punto 3 sea crítico, no opcional.

**5. Falla en silencio.**
Cuando no hay destinatario, el evento se marca `skipped` sin dejar rastro visible. Y cuando el
envío falla de verdad, tampoco: la alerta `email_delivery_failed` existe para el correo, **no
hay equivalente para las notificaciones**.

## Alcance

| Dentro | Fuera |
|---|---|
| Proveedor de Telegram configurado y verificado | El recordatorio de licencias (spec B) |
| Que el vínculo de usuario llegue a donde el job lee | WhatsApp / Meta como canal |
| Que el médico pueda vincularse | Rediseñar la cola de notificaciones |
| Visibilidad de "quién no puede recibir avisos" | Las 92 filas atascadas: se resuelven con criterio, no se borran a ciegas |
| Que un fallo deje alerta visible | El bot conversacional y sus funciones |

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | **Telegram es el único canal** | Decisión explícita del usuario; no se construye WhatsApp |
| 2 | Se arregla **en su propio spec**, antes que el de licencias | Es un bug de infraestructura; si va junto, la función nueva nace rota |
| 3 | Los vínculos de usuario deben quedar donde el job los lea | Hoy se guardan en un sitio y se leen en otro |
| 4 | Sin destinatario ⇒ **aviso visible**, no silencio | El fallo silencioso es la causa de que esto llevara un mes sin detectarse |
| 5 | Las 92 filas atascadas **no se borran** | Son evidencia; se reprocesan o se marcan con criterio y quedan auditadas |
| 6 | **Dos bots con roles separados** (confirmado por el usuario) | `@TurnosMedicosBot` = canal: lo comparten **médicos, encargados y admins**. `@MedicalSchedule_bot` = asistente: **solo encargados y admins** |
| 7 | El **staff se vincula a los dos**: al canal para recibir avisos, al asistente para consultar | Hoy solo se vincula al asistente, que es justo el que **no** envía |
| 8 | Se reutiliza el permiso **`receive_escalation_alerts`** ✅ confirmado | Los que ya reciben escalaciones son exactamente los que deben recibir estos avisos; crear un permiso nuevo no aporta |
| 9 | **El acuse al encargado entra en esta spec** ✅ confirmado | Cuando un médico responde por Telegram, el aviso al encargado se crea con `status="skipped"` (nace desactivado). Es el mismo tipo de bug —un aviso que no sale— y así el canal queda entero de una vez |

> **Por qué dos bots y no uno.** El asistente ya está restringido a staff
> (`_TELEGRAM_LINKABLE_ROLES = {"admin", "encargado"}`), y **un médico no es un usuario del
> sistema**: `UserRole` solo tiene `admin` y `encargado`. Separar el canal transaccional de la
> herramienta de consulta es el patrón correcto; un solo bot obligaría a los médicos a convivir
> con un asistente que no pueden usar.

## Requisitos

- **R1** — Existe un token de bot de notificaciones configurado en producción, y el proveedor
  deja de ser `FakeProvider`.
- **R2** — El vínculo entre un usuario del sistema y su Telegram queda **en el dato que el job
  consulta**. Un encargado vinculado recibe el aviso.
- **R3** — Un médico puede vincular su Telegram (requiere el bot de notificaciones activo y su
  webhook registrado).
- **R4** — Cuando no hay destinatario, **no se falla en silencio**: queda un registro y una
  alerta visible en la campana.
- **R5** — Cuando el proveedor rechaza un envío, queda una alerta visible (equivalente a la que
  ya existe para el correo).
- **R6** — Existe una forma de ver **quién puede y quién no puede recibir avisos**, sin consultar
  la base a mano.
- **R7** — Las 92 notificaciones y 92 confirmaciones atascadas quedan en un estado coherente y
  auditable, con un criterio explícito (no un borrado masivo).
- **R8** — Sin cambios en el comportamiento del bot conversacional.
- **R9** — El enlace de vinculación del **staff** apunta al bot **de notificaciones**, no al
  asistente. Requiere una configuración nueva con el nombre de usuario de ese bot
  (`telegram_notification_bot_username`), que hoy no existe.
- **R10** — El staff puede estar vinculado **a los dos bots a la vez**, sin que uno pise al otro.
- **R11** — Cuando un médico responde a un aviso, el encargado **recibe el acuse**: hoy el evento
  se crea con `status="skipped"` y nunca sale.

## Criterios de aceptación

**AC1 — El proveedor es real**
- **Dado** producción, **entonces** el proveedor activo **no** es `fake`, y un envío de prueba
  llega a un chat real.

**AC2 — Un encargado recibe**
- **Dado** un encargado con su Telegram vinculado y el permiso de escalación,
- **cuando** hay una confirmación vencida,
- **entonces** el mensaje **le llega** y el evento queda `sent` con proveedor `telegram`.

**AC3 — Un médico recibe**
- **Dado** un médico vinculado,
- **cuando** se aprueba la semana en la que está asignado,
- **entonces** recibe el aviso y su confirmación deja de estar huérfana.

**AC4 — El silencio se acaba**
- **Dado** un médico sin Telegram vinculado,
- **cuando** se aprueba una semana que lo incluye,
- **entonces** **no** se genera una confirmación que nadie verá sin más: queda una alerta visible
  del tipo *"no se pudo avisar a X: sin Telegram vinculado"*.

**AC5 — Se ve quién no puede recibir**
- **Dada** la pantalla correspondiente,
- **entonces** se distingue de un vistazo a los médicos y usuarios **sin** Telegram vinculado.

**AC6 — El acuse llega**
- **Dado** un médico que responde a un aviso por Telegram,
- **entonces** el encargado **recibe** el aviso de que respondió (hoy se crea con `skipped` y no sale).

**AC7 — El atasco queda resuelto**
- **Dadas** las 92 notificaciones y 92 confirmaciones del 9-10 de septiembre,
- **entonces** ninguna queda `pending` indefinidamente y el criterio aplicado queda documentado.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Configurar el token y **seguir** sin entregar, por el bug del vínculo | Se arreglan las dos cosas en el mismo cambio; AC2 lo verifica de punta a punta |
| Resolver el atasco borrando y perder la evidencia | Decisión 5: no se borra; se marca con criterio y queda auditado |
| Reprocesar 92 avisos viejos y **bombardear** con mensajes de septiembre | Los atascados **no** se reenvían: se cierran. Solo los nuevos se entregan |
| Depender de un solo canal | Es la decisión explícita (1). A cambio, R4/R6 hacen visible cuándo no se puede entregar |

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Bug | Se documenta que el canal de avisos por Telegram está inoperante en producción por tres causas independientes —proveedor ausente, vínculo de usuario guardado donde el job no lo lee, y bot de notificaciones inexistente—, con 92 notificaciones y 92 confirmaciones atascadas desde septiembre. Se decide Telegram como único canal y se arregla antes de construir el recordatorio de licencias. |
| 1.1.0 | 2026-10-10 | — | Implementación | **Causa raíz encontrada**: los jobs del scheduler reventaban con `NoReferencedTableError` porque `models/__init__.py` importaba 2 de 31 modelos y el worker no importa rutas; reportaban ceros, y eso ocultó el fallo durante un mes. Se corrige el registro de modelos y se añade un test de regresión en proceso limpio. Además: el webhook del bot se repunta de staging (404) a producción, el enlace del staff apunta al bot de avisos, el bot de avisos atiende `/start <token>`, el acuse al encargado deja de nacer `skipped`, y un aviso sin destinatario deja alerta visible. |
