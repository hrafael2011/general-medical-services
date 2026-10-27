---
spec: vinculacion-y-confirmaciones-telegram
version: 1.0.0
status: accepted
created: 2026-10-27
updated: 2026-10-27
---

# Spec — Vinculación segura y confirmaciones confiables por Telegram

**Tareas de implementación:** [2026-10-27-vinculacion-y-confirmaciones-telegram-tasks.md](2026-10-27-vinculacion-y-confirmaciones-telegram-tasks.md)

## Goal

Que un médico vinculado reciba el aviso de su turno y pueda confirmarlo por Telegram sin
ambigüedades, y que el sistema no finja haber avisado ni haber confirmado cuando no lo hizo.

## Contexto

El canal de avisos ya está construido y vivo: token del bot en API y worker, webhook registrado,
worker cron cada 30 minutos y jobs que corren sin crash. El problema medido el **2026-10-27** no
es el canal, sino tres cosas:

| Medición | Resultado |
|---|---|
| Médicos con Telegram vinculado | **0 de 74** (los 74 tienen `whatsapp_phone`) |
| Usuarios con Telegram vinculado | **0 de 6** |
| Notificaciones | 92 `skipped` de septiembre, **0 pendientes** |
| Confirmaciones | 92 `expired` de septiembre, **0 pendientes** |
| Webhook del bot | ✅ producción, `pending_update_count: 0`, sin errores |
| Worker | ✅ corre cada 30 min, los 5 jobs terminan sin crash |

Además, la revisión del código encontró defectos que aparecerán en cuanto haya vínculos:

1. La vinculación por teléfono compara solo los últimos 8 dígitos y **no muestra el nombre**;
   un error puede vincular al médico equivocado en silencio.
2. El botón de confirmación **no verifica** que quien lo pulsa sea el médico dueño.
3. Si la confirmación ya venció, el botón igual responde “✅ Asistencia confirmada” y no guarda nada.
4. El vencimiento se calcula como **aprobación + 12 h**, no respecto al servicio. Si la semana se
   aprueba con días de anticipación, la confirmación vence mucho antes del turno.
5. El recordatorio de 12 h solo adjunta botón si la confirmación sigue pendiente; con el cálculo
   actual casi siempre llega sin botón y con el texto “Responda 1”, que el bot no interpreta.
6. La escalación busca confirmaciones de más de **24 h**, pero estas vencen a las **12 h**: nunca
   se dispara.
7. La aprobación del calendario completo envía el **UUID del área** y no la hora.
8. No existe forma de revocar el canal de avisos de un usuario ni de desvincular a un médico.
9. `FEATURE_NOTIFICATIONS` está en `true` en la API y `false` en el worker; los jobs no lo leen.

Referencia del canal: [2026-10-09-reparar-canal-avisos-telegram.md](2026-10-09-reparar-canal-avisos-telegram.md).

## Decisiones

| # | Decisión | Razón |
|---|---|---|
| 1 | **Solo se confirma; no hay rechazo ni “No puedo”** | Decisión explícita del usuario (2026-10-27). No se construye botón de rechazo. |
| 2 | El botón inline de Telegram es la vía principal | Ya existe y es el canal decidido. |
| 3 | El link público es **opcional** y complementario | Sirve cuando el botón no está disponible; quien tenga el link puede confirmar. |
| 4 | Emparejamiento **exacto primero** y últimos 8 dígitos solo si hay un único candidato | Evita vincular al médico equivocado. |
| 5 | Se muestra el **nombre del médico** antes de vincular | Convierte un error silencioso en una confirmación visible. |
| 6 | El botón verifica que el `chat_id` pertenezca al médico de la confirmación | Cierra confirmaciones a nombre de otro. |
| 7 | El ciclo se ata al **inicio del servicio**: recordatorio T-12 h, escalación T-8 h, vencimiento T-4 h | Da tiempo al médico y al encargado, y hace que la escalación sea alcanzable. |
| 8 | Los tiempos son configurables | Permiten ajustar operación sin tocar código. |
| 9 | Desvincular es una acción explícita y auditada | Hoy un error de vinculación solo se corrige tocando la base. |
| 10 | Vincular médicos y encargados es **requisito operativo**, no código | Sin vínculos, el canal no entrega nada. |

## Alcance

| Dentro | Fuera |
|---|---|
| Emparejamiento de teléfono seguro y confirmación por nombre | Botón de rechazo o de “no puedo” |
| Verificación de propiedad del botón y mensajes de resultado | Rediseño visual del bot |
| Vencimiento, recordatorio y escalación atados al servicio | Segundo canal (WhatsApp, SMS, email) |
| Nombre y hora del área en la aprobación completa | Cambiar el flujo de aprobación de calendarios |
| Revocar canal de avisos y desvincular médico | Borrado masivo de vínculos |
| Link público opcional en el mensaje | Autenticación de médicos en la web |
| Alineación de `FEATURE_NOTIFICATIONS` y latencia del cron | Reemplazar el worker cron por un proceso permanente |

## Requisitos

- **R1** — La búsqueda de médico por teléfono usa coincidencia exacta del número normalizado y, si
  no hay exacta, últimos 8 dígitos **solo cuando hay un único candidato**. Si hay ambigüedad, no
  vincula.
- **R2** — Antes de vincular, el bot muestra el **nombre del médico** y pide confirmación.
- **R3** — El botón de confirmación solo se procesa si el `chat_id` que pulsa está vinculado al
  `doctor_id` de la confirmación.
- **R4** — Si la confirmación no existe, ya fue respondida, venció o no pertenece al médico, el
  mensaje lo dice y **no** muestra “Asistencia confirmada”.
- **R5** — El `due_at` de una confirmación de servicio o misión se calcula respecto al **inicio del
  servicio/misión**: `inicio - 4 h`. Si no hay hora conocida, se conserva el fallback actual.
- **R6** — El recordatorio T-12 h siempre lleva botón: si no hay confirmación pendiente, crea una
  nueva con el mismo cálculo de R5. El texto deja de pedir “Responda 1”.
- **R7** — La escalación se dispara para confirmaciones pendientes cuyo `due_at` cae dentro de las
  próximas 4 h (es decir, T-8 h respecto al servicio), y no vuelve a escalar la misma solicitud.
- **R8** — La aprobación del calendario completo resuelve el **nombre del área** y la **hora**,
  igual que la aprobación por semana.
- **R9** — Un admin puede **revocar el canal de avisos** de un usuario y **desvincular** a un
  médico; ambas acciones quedan auditadas.
- **R10** — `FEATURE_NOTIFICATIONS` es consistente entre API y worker, o deja de existir en el
  worker.
- **R11** — Opcional: el mensaje de Telegram incluye el link público de confirmación.
- **R12** — El flujo se valida de punta a punta con al menos un médico y un encargado vinculados.

## Criterios de aceptación

**AC1 — Vinculación sin ambigüedad**
- **Dado** un teléfono que coincide exactamente con un médico, **entonces** el bot muestra su
  nombre y pide confirmación.
- **Dado** un teléfono que coincide con dos médicos por últimos 8 dígitos, **entonces** no vincula
  y pide contactar al encargado.

**AC2 — Solo confirma el dueño**
- **Dado** un chat vinculado al médico A, **cuando** pulsa el botón de una confirmación del médico B,
  **entonces** no se guarda y recibe “No autorizado”.

**AC3 — Resultado honesto**
- **Dada** una confirmación vencida, **cuando** el médico pulsa el botón, **entonces** recibe
  “Esta confirmación ya venció” y el estado sigue `expired`.

**AC4 — Ciclo atado al servicio**
- **Dado** un servicio que empieza a las 08:00 del día D, **entonces** la confirmación vence a las
  04:00, se escala a las 00:00 y el recordatorio se envía a las 20:00 del día D-1.

**AC5 — Recordatorio con botón**
- **Dado** un médico vinculado con un servicio en 12 h, **cuando** corre el job de recordatorios,
  **entonces** el mensaje lleva botón de confirmación aunque la confirmación original hubiera
  vencido.

**AC6 — Escalación alcanzable**
- **Dada** una confirmación pendiente cuyo servicio empieza en 8 h, **cuando** corre el job de
  escalación, **entonces** el encargado recibe el mensaje consolidado y `escalated_at` queda
  escrito.

**AC7 — Mensaje con nombre y hora**
- **Dada** la aprobación de un calendario completo, **entonces** el mensaje dice el nombre del área
  y la hora del servicio, no el UUID.

**AC8 — Revocación**
- **Dado** un usuario con `telegram_chat_id`, **cuando** un admin revoca su canal, **entonces** el
  campo queda nulo y el evento de auditoría registra el cambio.
- **Dado** un médico vinculado, **cuando** un admin lo desvincula, **entonces**
  `doctors.telegram_chat_id` queda nulo y el siguiente aviso genera alerta de “sin destinatario”.

**AC9 — Operación real**
- **Dado** al menos un médico y un encargado vinculados, **cuando** se aprueba una semana con ese
  médico, **entonces** el aviso queda `sent` con proveedor `telegram`, el médico confirma y el
  encargado recibe el acuse.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambiar el cálculo de `due_at` afecta confirmaciones creadas con la regla vieja | Solo hay filas históricas `expired`; las nuevas usan la regla nueva. No se reprocesan. |
| El recordatorio crea una confirmación duplicada | Clave de idempotencia `reminder:{assignment}:{doctor}:{fecha}` y búsqueda previa de pendiente. |
| La escalación se dispara dos veces | Se mantiene `escalated_at` y se marca en la misma transacción. |
| El link público permite confirmar a quien lo reenvíe | Es opcional; se documenta como llave portable. La vía principal sigue siendo el botón. |
| Revocar por error deja a alguien sin avisos | Queda auditado y se puede volver a vincular con un link nuevo. |
| La prueba real depende de personas | Es la Fase 0 y la Fase 5; el código se prueba con tests mientras tanto. |

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-27 | — | Revisión del canal | Se documentan los defectos de vinculación y del ciclo de confirmación, y se decide el flujo: solo confirmar, nombre antes de vincular, propiedad del botón, tiempos atados al servicio y desvinculación auditada. |
| 1.1.0 | 2026-10-27 | — | Implementación | R1–R11 implementados con tests (ver el registro de avance de las tasks) y **desplegados**: API `9c4c6728` y worker `19c97b11` sobre `433cb14`. R12 **pendiente**: siguen 0 de 74 médicos y 0 de 6 usuarios vinculados, así que la prueba real de punta a punta espera a que una persona abra el bot. El estado no pasa a `implemented` hasta que AC9 se cumpla con datos reales. |
