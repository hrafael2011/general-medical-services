---
spec: cobertura-obligatoria-aprobacion
version: 1.0.0
status: proposed
created: 2026-11-01
updated: 2026-11-01
---

# Spec — Cobertura obligatoria para aprobar

**Tareas de implementación:** pendiente de crear al aprobar el alcance.

## Goal

Que no se pueda aprobar una semana con un día vacío o con un área sin médico, y que el rechazo
diga exactamente qué días y qué áreas faltan.

## Regla

Para aprobar una semana, **cada día** de esa semana debe tener al menos un médico en **cada área
requerida**. Si falta una sola combinación día × área, la aprobación se rechaza.

## Contexto — cómo está hoy

Verificado el **2026-11-01** leyendo el código:

| Punto | Comportamiento actual |
|---|---|
| `approve_week` ([service.py:376](../../backend/app/application/calendars/service.py)) | Solo exige que haya **al menos un turno** en la semana (`week_empty`). Un médico el lunes y nada el resto de la semana se aprueba igual |
| `approve_version` ([service.py:182](../../backend/app/application/calendars/service.py)) | **No valida nada**: puede aprobar un calendario sin un solo turno |
| Días sueltos vacíos | No se detectan, no se registran, no se avisan |
| Área vacía en un día con médicos en otras | Igual: no existe el concepto |

### Por qué se escapa

1. **La bandera existe y está muerta.** `ServiceAreaModel.required_for_daily_coverage` está en el
   catálogo de áreas y **ningún código de la aplicación la lee**; solo aparece en tests.
2. **Los "huecos" solo los crea la generación automática.** La tabla `unresolved_gaps` se llena en
   [generation_service.py:232](../../backend/app/application/calendars/generation_service.py). En
   modo manual —el que se usa— asignar a mano **no crea ni borra huecos**, así que la rejilla puede
   decir "sin huecos" con la semana vacía.
3. **El botón Aprobar no sabe cuántos médicos hay**
   ([CalendarGrid.tsx:605](../../frontend/src/features/calendars/CalendarGrid.tsx)): solo mira que
   la semana esté en borrador.
4. **La aprobación del calendario completo ni pasa por el control de semana**: va directo a
   `approve_version`.

### Las áreas de hoy

`Emergencia`, `Pista`, `Disponible` — las tres activas, las tres con `required_for_daily_coverage`
en `true`, las tres con hora de inicio 07:00.

Son **21 turnos por semana** (3 áreas × 7 días) y ~90 al mes. Con 70 médicos y tope de 3 servicios
cada uno, la capacidad es 210: sobra.

## Decisiones

| # | Decisión | Razón |
|---|---|---|
| 1 | Se exige cobertura **día × área**, no solo "algún médico ese día" | Es la regla del negocio: no puede quedar un área sin cubrir |
| 2 | Solo se exigen los días que caen **dentro del mes del calendario** | Las semanas son lunes-domingo y la última puede invadir el mes siguiente; esos días pertenecen a otro calendario |
| 3 | El área cuenta si está `active` **y** `required_for_daily_coverage` | Usa la bandera que hoy está muerta; permite marcar áreas que no cubren a diario |
| 4 | Se **bloquea** la aprobación, no se advierte | Aprobar publica y notifica; una advertencia no detiene el error |
| 5 | El rechazo lleva el detalle estructurado además del texto | La pantalla puede listarlo como panel; un toast con 20 líneas no se lee |
| 6 | Sin efecto retroactivo | Los calendarios ya aprobados no se revalidan |

## Requisitos

- **R1** — `approve_week` rechaza si algún día de la semana (dentro del mes) no tiene médico en
  alguna área requerida.
- **R2** — `approve_version` rechaza si algún día del mes no tiene médico en alguna área requerida.
- **R3** — El error incluye la lista de días y áreas que faltan.
- **R4** — El mensaje nombra el día en español y la fecha (`lunes 04/05`) y las áreas que faltan.
- **R5** — La pantalla muestra la lista, no solo un texto genérico.
- **R6** — Una semana completa (3 áreas × 7 días) se aprueba como hoy.
- **R7** — Los días del mes siguiente que caen en la última semana no se reclaman.

## Mensaje

> No se puede aprobar: faltan médicos en **lunes 04/05** (Disponible); **martes 05/05**
> (Emergencia, Pista).

Forma estructurada que acompañará al texto:

```json
{
  "code": "week_incomplete",
  "message": "No se puede aprobar: faltan médicos en lunes 04/05 (Disponible)…",
  "details": [
    { "date": "2026-05-04", "areas": ["Disponible"] },
    { "date": "2026-05-05", "areas": ["Emergencia", "Pista"] }
  ]
}
```

## Impacto

**13 llamadas a `approve_week` / `approve_version` en 4 archivos de pruebas** van a empezar a
fallar: sus fixtures aprueban calendarios con uno o dos turnos y ahora se rechazan. Hay que rehacer
esas fixtures con cobertura realista.

Ese es el grueso del trabajo; la regla en sí son dos comprobaciones.

Archivos afectados:
- `backend/tests/calendars/test_week_service.py`
- `backend/tests/calendars/test_calendar_service.py`
- `backend/tests/calendars/test_calendar_routes.py`
- `backend/tests/calendars/test_week_routes.py`

## Criterios de aceptación

**AC1 — Día vacío bloquea**
- **Dado** una semana con el miércoles sin médicos, **cuando** se aprueba, **entonces** se rechaza
  con `week_incomplete` y el miércoles aparece en el detalle.

**AC2 — Área vacía bloquea**
- **Dado** una semana con todas las fechas cubiertas en Emergencia y Pista pero sin Disponible,
  **cuando** se aprueba, **entonces** se rechaza y el detalle lista `Disponible` en los siete días.

**AC3 — Semana completa aprueba**
- **Dado** una semana con las 21 combinaciones cubiertas, **cuando** se aprueba, **entonces** se
  aprueba y se notifica como hoy.

**AC4 — Calendario completo**
- **Dado** un calendario con un día del mes sin cubrir, **cuando** se aprueba el calendario entero,
  **entonces** se rechaza con `calendar_incomplete`.

**AC5 — El borde del mes**
- **Dada** una semana que termina en el mes siguiente, **cuando** se aprueba, **entonces** los días
  del mes siguiente no se reclaman.

**AC6 — La pantalla lo dice**
- **Dado** un rechazo por cobertura, **cuando** la pantalla recibe la respuesta, **entonces** muestra
  la lista de días y áreas, no solo un texto genérico.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Bloquea aprobaciones legítimas de meses antiguos con datos incompletos | Se puede añadir un permiso de excepción, o marcar el calendario como histórico |
| Ralentiza la aprobación si el mes tiene muchos huecos | La lista se limita en pantalla a los primeros N, con el total |
| Un área nueva se crea como requerida y rompe calendarios en curso | La bandera se revisa al crear el área; queda como decisión de catálogo |
| Las fixtures de pruebas se vuelven pesadas | Se crea un ayudante que genera las 21 combinaciones de una semana |

## Relación con otros specs

- [2026-11-01-aprobacion-segura-notificaciones](2026-11-01-aprobacion-segura-notificaciones.md) —
  P1/P2/P3 ya implementados (deshacer cancela, margen de 24 h,
  re-aprobar avisa). Su **P4 "Vista previa de la aprobación"** (C1–C3) es la mitad visible de esta
  regla: conviene hacerlos juntos.

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-11-01 | — | Revisión pedida por el usuario | Se documenta que aprobar no valida cobertura: una semana vacía se bloquea, pero un día o un área vacía no; y aprobar el calendario completo no valida nada. Se fija la regla día × área y su impacto en pruebas. |
