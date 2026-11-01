# Tareas — Cobertura obligatoria para aprobar

**Spec:** [2026-11-01-cobertura-obligatoria-aprobacion.md](2026-11-01-cobertura-obligatoria-aprobacion.md)

**Estado:** ✅ Implementado (R1–R7, AC1–AC6)

**Rama:** `development`

---

## Resumen

Aprobar una semana o un calendario ahora exige que **cada día del período tenga al menos un
médico en cada área requerida**. El rechazo es `422` con `code` (`week_incomplete` /
`calendar_incomplete`), un texto en español y una lista estructurada en `details`.

La regla vive en el dominio (`backend/app/domain/calendars/coverage.py`) y el servicio solo la
consulta; el cálculo no conoce HTTP ni la base de datos.

---

## Fase 1 — Dominio

- [x] **Paso 1** — Test que falla: `backend/tests/calendars/test_coverage.py`
      (9 casos: semana completa, día vacío, área vacía, rango parcial, sin áreas requeridas,
      forma del detalle, mensaje corto y mensaje resumido).
- [x] **Paso 2** — Verificar que falla: `ModuleNotFoundError: ...coverage`.
- [x] **Paso 3** — Implementar `backend/app/domain/calendars/coverage.py`:
      `RequiredArea`, `CoverageGap`, `find_coverage_gaps()`, `format_coverage_message()`.
- [x] **Paso 4** — Verde: 9 pasan.

## Fase 2 — Servicio

- [x] **Paso 5** — Test que falla: `backend/tests/calendars/test_approve_coverage.py`
      (7 casos: día vacío, área vacía, semana completa, borde de mes, área no requerida,
      mes incompleto, mes completo).
- [x] **Paso 6** — Verificar el rojo: 3 de los 7 fallan por «DID NOT RAISE»; los otros 4 son
      guardas de no-regresión y ya pasaban.
- [x] **Paso 7** — `CalendarServiceError` acepta `details: list | None`.
- [x] **Paso 8** — `CalendarService._coverage_gaps()` y `_month_bounds()`; la regla se aplica en
      `approve_week` (recortando al mes del calendario) y en `approve_version` (mes completo).
- [x] **Paso 9** — Verde: 7 pasan.

## Fase 3 — API

- [x] **Paso 10** — Test que falla: `test_week_routes.py::test_approve_week_rejects_incomplete_coverage`.
- [x] **Paso 11** — Verificar el rojo: `KeyError: 'details'` (se comprobó revirtiendo `_http_exc`).
- [x] **Paso 12** — `_http_exc` añade `details` cuando existe; `week_incomplete` y
      `calendar_incomplete` mapeados a `422`.
- [x] **Paso 13** — Verde, más el camino feliz `test_approve_week_passes_with_full_coverage`
      (3 áreas × 7 días → 200).

## Fase 4 — Pantalla

- [x] **Paso 14** — Test que falla: `CalendarGrid.test.tsx`
      «lista los días y áreas que faltan cuando la aprobación se rechaza».
- [x] **Paso 15** — Verificar el rojo: el panel no aparece (timeout de 5 s).
- [x] **Paso 16** — Panel `coverage-gaps` con `lunes 18/05 — Disponible`, botón «Entendido»,
      y `coverageGapsFromError()` leyendo `ApiError.detail.details`.
- [x] **Paso 17** — Verde: 27 pruebas del archivo; 152 en todo el frontend; `tsc -b` limpio.

## Fase 5 — Ajuste de fixtures

- [x] **Paso 18** — `FakeWeekRepo.list_service_areas() → []` en `test_week_service.py`.
- [x] **Paso 19** — `_seed_assignment_parents` de `test_calendar_service.py` siembra su área con
      `required_for_daily_coverage=False`.
- [x] **Paso 20** — `_seed_service_area` de `test_week_routes.py` gana el parámetro
      `required_for_daily_coverage` (por defecto `False`).
- [x] **Paso 21** — El e2e del flujo manual pasa a esperar `week_incomplete`.

---

## Desviaciones del plan

| # | Lo planeado | Lo que se hizo | Por qué |
|---|---|---|---|
| 1 | 13 llamadas en 4 archivos romperían | **5 pruebas** rompieron, en 3 archivos | La mayoría de los `approve_*` no llega a la validación (estado ya aprobado) o su área sembrada no era requerida. La estimación del spec era alta |
| 2 | El e2e seguiría aprobando la semana | Ahora espera `422 week_incomplete` | Su seed solo permite el área Emergencia y ningún médico cubre el domingo: con la regla nueva la semana **no se puede** aprobar. Forzar un 200 habría exigido inventar cobertura |
| 3 | — | El mensaje nombra como mucho 7 días y resume el resto | Con el mes vacío, la frase completa eran 31 entradas ilegibles. `details` sigue llevando todas |
| 4 | — | `_month_bounds()` usa `calendar.monthrange` | Evita recalcular el fin de mes a mano y respeta los meses de 28/29 días |
| 5 | «se bloquea la aprobación» | Se valida **antes** de mutar estado | La semana y la versión siguen en `draft` tras el rechazo; la prueba lo verifica |

## Archivos tocados

**Producción**

- `backend/app/domain/calendars/coverage.py` (nuevo)
- `backend/app/application/calendars/errors.py`
- `backend/app/application/calendars/service.py`
- `backend/app/api/routes/calendars.py`
- `frontend/src/features/calendars/CalendarGrid.tsx`

**Pruebas**

- `backend/tests/calendars/test_coverage.py` (nuevo)
- `backend/tests/calendars/test_approve_coverage.py` (nuevo)
- `backend/tests/calendars/test_week_routes.py`
- `backend/tests/calendars/test_week_service.py`
- `backend/tests/calendars/test_calendar_service.py`
- `backend/tests/e2e/test_api_calendar_manual_flow.py`
- `frontend/src/features/calendars/CalendarGrid.test.tsx`

## Verificación

| Suite | Resultado |
|---|---|
| `tests/calendars` | 216 pasan |
| `tests/e2e tests/notifications tests/confirmations` | 67 pasan |
| `tests/e2e -m "e2e or not e2e"` | 2 pasan |
| Backend completo | ver commit |
| Frontend (`vitest run`) | 152 pasan |
| `tsc -b` | limpio |

## Pendiente / fuera de alcance

- P4 del spec de aprobación segura (vista previa de la aprobación) — se solapa con esta regla y
  conviene hacerlo justo después.
- Permiso de excepción o marca de «calendario histórico» para meses antiguos incompletos
  (riesgo identificado en el spec, no implementado).
- Revisar la bandera `required_for_daily_coverage` al crear un área nueva desde Catálogos
  (hoy se puede marcar sin avisar de que endurece la aprobación).
