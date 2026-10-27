---
spec: gestion-vinculos-telegram
version: 1.0.0
status: accepted
created: 2026-10-27
updated: 2026-10-27
---

# Spec — Generación de vínculos de Telegram por rol

**Tareas de implementación:** [2026-10-27-gestion-vinculos-telegram-tasks.md](2026-10-27-gestion-vinculos-telegram-tasks.md)

## Goal

Que cualquiera pueda generar el enlace de la persona correcta desde la pantalla de Telegram —sin
listas vacías, sin campos del bot asistente— y que la regla de quién puede generar qué la aplique
el backend, no solo la interfaz.

## Contexto

Medido el **2026-10-27** en producción:

| Medición | Resultado |
|---|---|
| Usuarios | 6: **1 superadmin** (`Administrador`), **1 admin no-superadmin** (`Dra. Alexandra Acosta`), 4 encargados |
| Usuarios vinculados al bot de avisos | **0 de 6** |
| Médicos vinculados | **1 de 74** (`MIGUELINA A. ACOSTA RAMOS`) |
| Enlaces generados | 0 |

Tres defectos concretos:

1. **El desplegable “Usuario del sistema” sale vacío.** La pantalla pide dos listas con un
   `Promise.all` ([TelegramLinks.tsx:97-102](../../frontend/src/features/telegram/TelegramLinks.tsx)):
   admins y encargados. Pero `GET /admin/users?role=admin` exige superadmin
   ([admin_users.py:56-61](../../backend/app/api/routes/admin_users.py)): con una cuenta admin normal
   devuelve **403**, el `Promise.all` rechaza entero y se pierde también la lista de encargados.
2. **La política de generación no se aplica.** El listado de admins es solo-superadmin, pero
   `POST /telegram/link-tokens` acepta cualquier `user_id` de rol admin o encargado. Un admin normal
   no puede *ver* a otros admins, pero podría generarles un enlace si conociera su UUID.
3. **La pantalla mezcla dos épocas.** Muestra el bloque “Vinculación manual” (ID Telegram, Usuario
   Telegram, ID Usuario) y la tabla de vínculos, que escriben y leen `telegram_user_links` — el
   vínculo del **bot asistente**. Nada de eso entrega avisos: el canal real es
   `users.telegram_chat_id`.

## Decisiones

| # | Decisión | Razón |
|---|---|---|
| 1 | Un **admin normal** genera su propio enlace y los de los **encargados** | Es lo que hoy permite la UI; se formaliza también en el backend. |
| 2 | Un **superadmin** genera enlaces para **todos**: admins y encargados | Necesita poder vincular a cualquier cuenta, incluida otra admin. |
| 3 | La regla se valida en el **backend** | La UI no es un control de acceso: el endpoint se llama directo. |
| 4 | La pantalla muestra **siempre al propio usuario** como opción | Si no puede listar admins, sin esto no podría generarse su propio enlace. |
| 5 | Un fallo al listar admins **no vacía** la lista de encargados | Un 403 accidental no debe dejar la pantalla inservible. |
| 6 | Se **retiran** el bloque de vinculación manual y la tabla de vínculos del asistente | Confunden: sugieren que vincularse ahí hace llegar los avisos. |
| 7 | `telegram_user_links` y su endpoint DELETE **no se tocan** | El asistente sigue funcionando; solo se retira la UI que lo administra. |
| 8 | El enlace sigue siendo de **un solo uso, 24 h**, y se abre desde el Telegram de la persona | Sin cambios en el mecanismo que ya funciona. |

## Alcance

| Dentro | Fuera |
|---|---|
| Política de generación aplicada en `POST /telegram/link-tokens` | Rediseño del bot o del asistente |
| Lista de destinatarios correcta y sin vaciarse por un 403 | Vincular automáticamente a nadie |
| Propio usuario siempre presente en la lista | Cambiar el flujo de `/start <token>` |
| Retiro del bloque manual y de la tabla del asistente | Borrar datos de `telegram_user_links` |
| Tests de backend y frontend de los tres puntos | Permisos nuevos o cambios de rol |

## Requisitos

- **R1** — `POST /telegram/link-tokens` devuelve **403** si el destinatario es un usuario con rol
  `admin`, no es el propio solicitante y este no es superadmin.
- **R2** — Un admin normal puede generar enlace **para sí mismo** y **para cualquier encargado**.
- **R3** — Un superadmin puede generar enlace para cualquier admin y cualquier encargado.
- **R4** — El destinatario debe seguir existiendo y tener rol `admin` o `encargado`
  (comportamiento actual de `_get_linkable_user`).
- **R5** — La pantalla pide la lista de admins **solo** cuando el usuario es superadmin.
- **R6** — Si la llamada de admins falla, la lista de encargados se muestra igual.
- **R7** — El propio usuario aparece siempre en el desplegable, marcado como “Yo”, con su estado
  real de vínculo.
- **R8** — Se eliminan de la pantalla el bloque “Vinculación manual” y la tabla de
  `telegram_user_links`.

## Criterios de aceptación

**AC1 — Admin normal, encargado**
- **Dado** un admin no-superadmin, **cuando** genera el enlace de un encargado, **entonces**
  recibe 201 con `deep_link_url` que apunta al bot de avisos.

**AC2 — Admin normal, otro admin**
- **Dado** un admin no-superadmin, **cuando** pide un enlace para otra cuenta admin, **entonces**
  recibe 403 y no se crea ningún token.

**AC3 — Admin normal, sí mismo**
- **Dado** un admin no-superadmin, **cuando** genera su propio enlace, **entonces** recibe 201.

**AC4 — Superadmin**
- **Dado** el superadmin, **cuando** genera el enlace de otra cuenta admin, **entonces** recibe 201.

**AC5 — Pantalla utilizable**
- **Dado** un admin no-superadmin con encargados en el sistema, **cuando** abre la pantalla de
  Telegram, **entonces** el desplegable muestra a los encargados y a él mismo, y no aparece ningún
  campo de ID de usuario ni la tabla de vínculos del asistente.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un admin normal necesita vincular a otra admin y queda bloqueado | Lo hace el superadmin; el 403 explica por qué. |
| Retirar la tabla deja vínculos del asistente sin administrar | El endpoint DELETE sigue existiendo; no se borran datos. |
| El usuario no ve el motivo de un 403 | El mensaje del backend se muestra en el toast de la pantalla. |
| Duplicar al propio usuario en la lista | Se compara por `id` antes de añadirlo. |

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-27 | — | Pantalla con desplegable vacío | Se formaliza la política de generación por rol, se corrige la lista que se vaciaba por un 403 y se retira la administración del vínculo del bot asistente. |
