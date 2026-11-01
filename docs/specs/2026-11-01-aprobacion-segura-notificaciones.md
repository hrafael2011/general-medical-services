---
spec: aprobacion-segura-notificaciones
version: 1.2.0
status: proposed
created: 2026-11-01
updated: 2026-11-01
---

# Spec — Aprobación segura y avisos reversibles

**Tareas de implementación:** [2026-11-01-aprobacion-segura-notificaciones-tasks.md](2026-11-01-aprobacion-segura-notificaciones-tasks.md)
(Fase 1 detallada; fases 2 y 3 se escriben al cerrar la 1).

## Goal

Que equivocarse al aprobar una semana no le llegue a los médicos, y que corregir un error sí
les llegue.

## Contexto

El **2026-10-27** se aprobó una semana por error y los avisos salieron a los médicos. Revisado el
código el **2026-11-01**, el problema no fue el clic: fue que **decidir y notificar son el mismo
acto**, y que deshacer la decisión no deshace el aviso.

### Lo que pasa hoy

1. **Aprobar** ([service.py:411](../../backend/app/application/calendars/service.py)) marca la
   semana como aprobada y encola un aviso por asignación
   ([triggers.py:181](../../backend/app/application/notifications/triggers.py)).
2. El worker (cron cada 10 min) envía lo que encuentra en la cola.
3. **Desbloquear** ([service.py:484](../../backend/app/application/calendars/service.py)) devuelve
   la semana a borrador, pero **no cancela los avisos ya encolados ni las confirmaciones**.
4. El resultado: el operador deshace, y los avisos salen igual.

No existe en todo el backend ninguna transición a `cancelled`: el único cierre de un aviso es
`sent`, `failed` o `skipped`.

### La palanca que ya existe

`notification_events.scheduled_for` **ya se respeta** al seleccionar pendientes
([notifications.py:75-77](../../backend/app/infrastructure/repositories/notifications.py)). Una
ventana de gracia no necesita infraestructura nueva: basta con escribir esa fecha al aprobar.

### Defecto adicional encontrado

`approve_calendar` omite **todas** las notificaciones si detecta un desbloqueo previo
(`version.reason.startswith("__unlock__")`,
[service.py:229](../../backend/app/application/calendars/service.py)). Es el problema inverso:
tras corregir un error, los médicos **no se enteran de la versión buena**.

## Decisiones

| # | Decisión | Razón |
|---|---|---|
| 1 | Desbloquear **cancela** los avisos no enviados | Deshacer debe deshacer |
| 2 | Nunca se toca un aviso `sent` ni `sending` | Lo enviado no se recupera; lo que está en vuelo puede duplicarse |
| 3 | La aprobación encola con 15 minutos de margen, configurable | Da tiempo real a arrepentirse |
| 4 | `scheduled_for` es el mecanismo; no se toca el worker | Ya funciona |
| 5 | Las confirmaciones de turnos cancelados se cancelan | Hoy quedan `pending` y escalan por un turno que no existe |
| 6 | Toda cancelación queda auditada | Sin rastro no se puede investigar |
| 7 | Re-aprobar tras corregir **sí** avisa de los cambios | Hoy calla todo |
| 8 | Un mensaje por médico y semana queda fuera de este cambio | Es un rediseño de plantillas, no una corrección |

## Requisitos

- **R1** — `unlock_week` cancela los avisos `pending` de la semana.
- **R2** — `unlock_calendar` cancela los avisos `pending` del calendario.
- **R3** — Los avisos admiten el estado `cancelled`; las confirmaciones también.
- **R4** — Al cancelar un aviso se cancela su confirmación asociada.
- **R5** — Al quitar una asignación aprobada se cancela su confirmación pendiente.
- **R6** — `approve_week` y `approve_calendar` encolan con `scheduled_for = ahora + margen`.
- **R7** — El margen es configurable (`approval_grace_minutes`, por defecto 15).
- **R8** — Es posible cancelar el envío antes de la hora programada, con o sin desbloquear.
- **R9** — La pantalla muestra el estado "Programada" mientras el envío no ha salido.
- **R10** — La pantalla dice cuántos avisos se cancelaron.
- **R11** — La aprobación del calendario completo tras un desbloqueo notifica los cambios reales.
- **R12** — Ningún aviso `sent` o `sending` se modifica por estas operaciones.

## Lista de arreglos, en orden de prioridad

### P1 — El error de aprobar

| # | Arreglo | Dónde |
|---|---|---|
| A1 | Desbloquear semana cancela los avisos no enviados | `unlock_week` |
| A2 | Desbloquear calendario cancela los avisos no enviados | `unlock_calendar` |
| A3 | Estado `cancelled` en avisos | `notification_events` |
| A4 | Cancelar las confirmaciones de esos turnos | `confirmation_requests` |
| D2 | Al quitar un turno aprobado, cancelar su confirmación | `on_calendar_assignment_removed_after_approval` |
| A5 | Auditoría de la cancelación | audit |
| A6 | Mostrar "Cancelados N avisos" en la pantalla | `CalendarGrid.tsx` |

### P2 — Los 15 minutos de margen

| # | Arreglo | Dónde |
|---|---|---|
| B1 | Configuración `approval_grace_minutes` | `config.py` |
| B2 | Encolar con hora de salida | `on_week_approved`, `on_calendar_approved` |
| B3 | Banner con cuenta atrás y "Cancelar envío" | UI |
| B4 | Endpoint para cancelar sin desbloquear | API |
| B5 | Estado visible "Programada" | UI |
| B6 | Ajustar el desfase del cron: el envío real cae entre 15 y 25 min | decisión |

### P3 — Que corregir sí avise

| # | Arreglo | Dónde |
|---|---|---|
| D3 | Re-aprobar tras desbloquear notifica los cambios (hoy calla todo) | `approve_calendar` |

### P4 — Ver antes de pulsar

| # | Arreglo |
|---|---|
| C1 | Vista previa de la aprobación: asignaciones, médicos, sin Telegram, mensaje exacto |
| C2 | Panel "Revisar y aprobar" |
| C3 | Mostrar los médicos sin Telegram antes, no después |

### P5 — Correcciones finas

| # | Arreglo |
|---|---|
| D1 | No mandar "removido" si el aviso original aún no salió |
| D4 | Mensaje de corrección explícito cuando el aviso ya salió |

### P6 — Ruido

| # | Arreglo |
|---|---|
| E1 | Un mensaje por médico por semana en vez de uno por turno |

### P7 — Opcional

| # | Arreglo |
|---|---|
| E2 | Doble firma para aprobar el calendario completo |
| E3 | Ventana horaria de envío (07:00–20:00) |

## Criterios de aceptación

**AC1 — Deshacer sin avisar**
- **Dado** una semana recién aprobada con avisos en cola, **cuando** se desbloquea,
  **entonces** no se envía ningún aviso de esa semana y las confirmaciones quedan canceladas.

**AC2 — Lo enviado no se toca**
- **Dado** un aviso ya enviado, **cuando** se desbloquea la semana, **entonces** su estado sigue
  `sent` y no se reenvía.

**AC3 — Margen**
- **Dada** una aprobación, **entonces** los avisos no salen antes de `approval_grace_minutes` y la
  pantalla muestra la hora de salida.

**AC4 — Cancelar a tiempo**
- **Dado** un envío programado, **cuando** se cancela antes de la hora, **entonces** no se envía y
  queda auditado con cuántos se cancelaron.

**AC5 — Corregir sí avisa**
- **Dado** un calendario desbloqueado, corregido y vuelto a aprobar, **cuando** se aprueba,
  **entonces** los médicos afectados reciben el aviso actualizado.

**AC6 — Sin confirmaciones fantasma**
- **Dado** un turno aprobado y luego quitado, **entonces** su confirmación no aparece en la
  escalación.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Cancelar un aviso que el worker está enviando | Solo se cancela `pending`; nunca `sending` ni `sent` |
| El margen retrasa avisos legítimos | 15 min frente a confirmaciones que se hacen con días de margen |
| Un servicio que empieza en menos de 24 h necesita aviso inmediato | Excepción: enviar de inmediato y permitir cancelar hasta el envío |
| D3 genere avisos duplicados al re-aprobar | Se mantiene la clave de idempotencia por asignación |
| Cambiar el estado de las confirmaciones afecta reportes históricos | Solo aplica a filas nuevas; no se reprocesa el histórico |

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-11-01 | — | Aprobación por error del 2026-10-27 | Se documenta que desbloquear no cancela los avisos, que no existe estado de cancelación, y que re-aprobar tras desbloquear no notifica. Se propone la lista de arreglos priorizada. |
| 1.1.0 | 2026-11-01 | — | Implementación de P1 | **P1 (A1–A6, D2) queda implementado**: desbloquear semana o calendario cancela los avisos `pending` y sus confirmaciones, sin tocar `sending` ni `sent`; quitar un turno aprobado cancela su confirmación; todo queda auditado; la pantalla informa cuántos se cancelaron. P2–P7 siguen pendientes. |
| 1.2.0 | 2026-11-01 | — | Implementación de P2 | **P2 (B1–B6) queda implementado**: aprobar encola con `scheduled_for = ahora + approval_grace_minutes` (15 por defecto); la pantalla muestra «N avisos programados — salen a las HH:MM» con un botón «Cancelar envío» que no deshace la aprobación; endpoints `GET …/notifications/pending` y `POST …/notifications/cancel`. El envío real cae entre 15 y 25 minutos por el cron de 10. P3–P7 siguen pendientes. |
