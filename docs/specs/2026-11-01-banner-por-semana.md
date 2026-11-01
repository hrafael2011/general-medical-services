---
spec: banner-por-semana
version: 1.1.0
status: implemented
created: 2026-11-01
updated: 2026-11-01
---

# Spec — Un aviso por semana, no un total

**Specs padres:**
[2026-11-01-aprobacion-segura-notificaciones.md](2026-11-01-aprobacion-segura-notificaciones.md) (P2) ·
[2026-11-01-ventana-24h-cuenta-atras.md](2026-11-01-ventana-24h-cuenta-atras.md)

## Goal

Que el operador vea **cada semana con su propia hora de envío**, en vez de un único total que
mezcla todas, y que pueda cancelar una sola.

## Contexto — cómo está hoy (2026-11-01)

El banner es único y suma todo:

> **24 avisos programados — se envía en 23 h 41 min**

Si apruebas la semana 1 hoy y la semana 2 doce horas después:

- el número sube a 24, pero **no aparece otro banner**;
- el contador sigue apuntando a la semana 1, así que la 2 no muestra cuándo sale;
- no se puede cancelar solo la 2: el botón cancela todas.

El caso es real: las semanas se aprueban en momentos distintos, y con una ventana de 24 h esas
horas quedan repartidas.

### El número también estaba inflado

Detectado el **2026-11-01** al revisar la semana 2: mostraba **41 avisos** para **21 turnos**.
Un turno podía tener dos avisos en cola —el «te asignaron» suelto y el de la aprobación—, así que
el contador sumaba mensajes, no turnos, y el médico recibía dos mensajes casi iguales.

Se corrigió en la raíz (ver changelog 1.6.0 del spec de aprobación segura): aprobar cancela los
avisos de asignación suelta pendientes. Con eso el número del grupo vuelve a coincidir con los
turnos de la semana.

### Lo que ya existe y sirve

- `GET /{calendar_id}/notifications/pending` → total y próxima hora.
- `POST /{calendar_id}/notifications/cancel` → cancela todos los pendientes.
- Los avisos apuntan al turno, y el turno tiene fecha.

### Lo que no se puede usar

`calendar_assignments.calendar_week_id` está **vacío en los 127 turnos** de la base local, así que
la semana se deduce por la fecha del turno contra los rangos de `calendar_weeks`, no por esa columna.

## Decisiones

| # | Decisión | Razón |
|---|---|---|
| 1 | La respuesta se agrupa **por semana**, con su propio `next_send_at` | Cada aprobación tiene su hora; mezclarlas esconde la segunda |
| 2 | Se mantiene el total y la próxima hora global | Una frase de resumen evita perder la vista de conjunto |
| 3 | Cancelar acepta una semana; sin semana, cancela todas | El caso de «me equivoqué solo en la 2» |
| 4 | La semana se deduce por la **fecha del turno** | La columna `calendar_week_id` no está poblada |
| 5 | Un aviso cuya fecha no cae en ninguna semana va a un grupo «Otros» | No se puede perder un aviso por no saber dónde ponerlo |
| 6 | Sin migración | Todo se calcula al leer |

## Requisitos

- **R1** — `GET …/notifications/pending` devuelve `groups`: una entrada por semana con `week_id`,
  `week_label`, `count` y `next_send_at`.
- **R2** — Se conservan `count` y `next_send_at` globales.
- **R3** — Los grupos salen ordenados por hora de envío (el primero que sale, primero).
- **R4** — `POST …/notifications/cancel` acepta `week_id` opcional; con él cancela solo esa semana.
- **R5** — La pantalla pinta un bloque por semana con su cuenta atrás y su botón.
- **R6** — Un grupo vacío no se muestra.
- **R7** — El total global sigue visible.

## Mensaje

```
28 avisos programados en total

Semana 1 (4–10 may) · 12 avisos · se envía en 3 h 20 min   [Cancelar]
Semana 2 (11–17 may) · 16 avisos · se envía en 15 h 20 min  [Cancelar]
```

## Criterios de aceptación

**AC1** — Dos semanas aprobadas con horas distintas producen dos grupos con horas distintas.
**AC2** — Cancelar el grupo de la semana 2 deja pendiente el de la semana 1.
**AC3** — El total coincide con la suma de los grupos.
**AC4** — Aprobando de nuevo una semana ya programada no se duplica su grupo.
**AC5** — Un aviso sin semana cae en «Otros» y se puede cancelar.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Agrupar por fecha es más lento que una columna | Se resuelve en memoria sobre los avisos pendientes, que son decenas |
| Dos versiones del calendario con semanas solapadas | Se usan las semanas de la versión de los turnos |
| Un grupo «Otros» confunde al operador | Solo aparece si de verdad hay avisos fuera de rango |

## Tareas

**Estado:** ✅ implementado.

- [x] Esquema: `PendingNotificationGroup`, `groups` en `PendingNotificationsRead` y
      `CancelPendingRequest`.
- [x] Ruta: `_group_by_week()` usando `list_weeks_by_version` y la fecha del turno.
- [x] Ruta: `cancel` con `week_id` opcional (404 si la semana no es de esa versión).
- [x] Frontend: un bloque por semana con su cuenta atrás y su botón; con una sola semana se
      mantiene la línea de siempre para no duplicar el número.
- [x] Pruebas: 3 de ruta (agrupación, total, cancelación parcial) y 1 de pantalla.

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-11-01 | — | Petición del usuario | El banner pasa de un total único a un bloque por semana, con hora y cancelación independientes. |
