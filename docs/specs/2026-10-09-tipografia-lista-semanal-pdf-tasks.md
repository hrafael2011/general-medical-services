# Tasks — Tipografía y dimensionado de la lista semanal en PDF

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-tipografia-lista-semanal-pdf.md](2026-10-09-tipografia-lista-semanal-pdf.md)

**Goal:** Letra más grande y filas con más aire en la lista semanal en PDF, sin deformar y sin
que aparezca una segunda página.

**Architecture:** `base.html` gana dos bloques de Jinja vacíos por defecto — `extra_styles`
(en el `<head>`) y `page_class` (en el contenedor `.page`) — para que una plantilla pueda
ajustar su propio dimensionado sin tocar a las demás. Solo `weekly_schedule.html` los
sobrescribe, con las 6 reglas acotadas por `.page--weekly-list`. El espacio necesario se
recupera del logo del encabezado y del hueco antes de las firmas, que estaban
sobredimensionados para un documento de 21 filas.

**Tech Stack:** Jinja2, WeasyPrint, CSS Paged Media, pytest

**Estado:** ✅ **Implementado** en la rama `feat/whatsapp-pdf-semanal` (2026-10-09).

**Evidencia de verificación:**

| Comprobación | Comando | Resultado |
|---|---|---|
| Páginas con la semana real (21 filas) | `pdfinfo` sobre el PDF del endpoint en vivo | **1 página** |
| Fin del contenido | `pdftotext -bbox` | **544.5 pt** de un límite de 555.6 (**mejor que antes**: 546.1) |
| Sin deformación | `pdftotext -layout` | **21 filas de asignación**, igual que antes |
| Aislamiento de los otros reportes | diff de tokens del CSS emitido | **0 diferencias de reglas** |
| Endpoint en vivo | `curl` autenticado | `HTTP 200 · 93 726 bytes · application/pdf` |
| Tests | `pytest tests/reports -q` | **81 passed** |

---

## Fase 1 — Puntos de extensión en la plantilla base

### Task 1.1 — Bloques de Jinja en `base.html`

**Archivo:** `backend/app/application/reports/templates/base.html`

- [x] **Añadir** `{% block extra_styles %}{% endblock %}` al final del `<style>`, precedido de
      un comentario de Jinja (`{# #}`) que no emite nada al CSS.
- [x] **Añadir** `{% block page_class %}{% endblock %}` a `<div class="page ...">`.
- [x] **Verificar** que para las plantillas que no los sobrescriben el CSS emitido es idéntico:
      comparado token por token contra el de `HEAD`, **0 diferencias**.

> Los bloques se dejaron vacíos por defecto a propósito: cualquier plantilla que no los
> implemente emite exactamente lo mismo que antes.

---

## Fase 2 — Estilos acotados de la lista semanal

### Task 2.1 — Clase de página y reglas

**Archivo:** `backend/app/application/reports/templates/weekly_schedule.html`

- [x] **Implementar** `{% block page_class %}page--weekly-list{% endblock %}`.
- [x] **Implementar** `{% block extra_styles %}` con las seis reglas:

```css
.page--weekly-list table { font-size: 8.5pt; }
.page--weekly-list thead th { font-size: 8pt; padding: 4px 9px; }
.page--weekly-list tbody td { font-size: 8.5pt; padding: 4px 9px; }
.page--weekly-list .day-cell { font-size: 9pt; }
.page--weekly-list .signature-block { margin-top: 20px; }
.page--weekly-list .header-logo { height: 96px; }
```

- [x] **Comprobar** que `coverage.html`, `workload.html` y `doctor_list.html` **no** definen
      ninguno de los dos bloques (grep sobre las tres fuentes).

> El logo no se deforma: la regla solo reduce la altura de la caja y la imagen usa
> `object-fit: contain`, así que escala manteniendo la proporción.

---

## Fase 3 — Verificación

### Task 3.1 — Medir contra la semana real

- [x] **Renderizar** la 1RA SEMANA de agosto 2026 (21 asignaciones, el máximo posible).
- [x] **Verificar** 1 página y el fin del contenido dentro del margen.
- [x] **Verificar** que el contenido termina **más arriba** que antes (544.5 vs 546.1): la letra
      creció y aun así sobra más espacio que en el estado previo.
- [x] **Verificar** por extracción de texto que siguen siendo **21 filas de asignación** — ningún
      nombre se partió en dos líneas.

### Task 3.2 — Verificar el aislamiento

- [x] **Renderizar** una plantilla hija que no sobrescribe estilos y comparar su CSS contra la
      versión de `HEAD`: **0 diferencias de reglas**. Eso cubre a cobertura, carga y lista de
      médicos, que solo definen el bloque `content`.

### Task 3.3 — Tests

- [x] **Añadir** `test_weekly_sizing_is_scoped_and_does_not_leak_to_other_reports`: verifica las
      6 reglas y que los tres reportes hermanos no sobrescriben los bloques.
- [x] `pytest tests/reports -q` → **81 passed**.

### Task 3.4 — Endpoint en vivo

- [x] **Llamar** al endpoint real con la semana aprobada → `HTTP 200`, 1 página.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué arregla | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 1 | Fase 1 | Puntos de extensión sin efecto por defecto | Bajo | ✅ hecho |
| 🔴 2 | Fase 2 | Los tamaños nuevos, acotados | Bajo | ✅ hecho |
| 🟠 3 | Fase 3 | Verificación y no-regresión | Bajo | ✅ hecho |

## Archivos tocados

| Archivo | Tipo |
|---|---|
| `backend/app/application/reports/templates/base.html` | modificado — dos bloques vacíos |
| `backend/app/application/reports/templates/weekly_schedule.html` | modificado — clase + 6 reglas |
| `backend/tests/reports/test_week_report_service.py` | modificado — test de aislamiento |

## Casillas abiertas

1. **Revisión visual del usuario** en el navegador — los números están verificados; falta su
   visto bueno estético sobre el hueco de las firmas.
2. **Cuarta área de servicio** (`[A VERIFICAR]`) — si algún día se agrega, el máximo pasa de 21 a
   28 filas y hay que rehacer la medición de página.
3. **Merge a `master`** — pendiente de autorización explícita.

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | Diagnóstico | Medido el estado previo: 21 filas = máximo, 9.5 pt libres, 9 combinaciones probadas, todas en 2 páginas. |
| 2026-10-09 | 1.1 | Bloques `extra_styles` y `page_class` en `base.html`, vacíos por defecto. |
| 2026-10-09 | 2.1 | 6 reglas acotadas a `.page--weekly-list`. |
| 2026-10-09 | 3.1 | 1 página, contenido hasta 544.5 pt, 21 filas sin partir. |
| 2026-10-09 | 3.2 / 3.3 | Aislamiento verificado (0 diferencias de reglas). 81 tests pasan. |
| 2026-10-09 | 3.4 | Endpoint en vivo: HTTP 200, 93 726 bytes, 1 página. |
