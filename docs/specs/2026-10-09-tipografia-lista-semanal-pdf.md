---
spec: tipografia-lista-semanal-pdf
version: 1.1.0
status: implementado
created: 2026-10-09
updated: 2026-10-09
---

# Spec — Tipografía y dimensionado de la lista semanal en PDF

## Goal

Que la información de la lista semanal en PDF se lea mejor: letra más grande y filas con más
aire vertical, **sin deformar** el documento y **sin que aparezca una segunda página**.

**Tareas de implementación:** [2026-10-09-tipografia-lista-semanal-pdf-tasks.md](2026-10-09-tipografia-lista-semanal-pdf-tasks.md)

## Contexto

Origen: pedido directo del usuario (2026-10-09), inmediatamente después de agregar la columna
`WHATSAPP / CEL`. Con una cuarta columna en la tabla, el documento quedó más apretado y el
encargado pidió más legibilidad.

**La restricción que gobierna todo:** una semana tiene como **máximo absoluto 21 filas**
(3 áreas de servicio × 7 días). No es un caso cualquiera: es el peor caso posible, y el
documento ya está diseñado para llenar la página con él.

### Medición del estado previo

| Medida | Valor |
|---|---|
| Alto de página (A4 horizontal) | 595.3 pt |
| Dónde terminaba el contenido | 546.1 pt |
| Límite antes de perder el margen inferior de 14 mm | 555.6 pt |
| **Espacio libre real** | **9.5 pt** |

Lo que se desborda primero no es la tabla: es el **bloque de firmas**, que al crecer la tabla
salta a la página 2. Se probaron 9 combinaciones subiendo solo la letra y **todas** terminaron
en 2 páginas.

## Alcance

| Dentro | Fuera |
|---|---|
| Lista semanal (`weekly_schedule.html`) | Los otros tres reportes que comparten `base.html` |
| Tamaños de letra, aire de fila, logo y hueco de firmas | Contenido, columnas y datos |
| Aislamiento de los estilos | La columna `WHATSAPP / CEL` (spec aparte) |

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | Recuperar espacio del **logo** (128px → 96px) | Está sobredimensionado para este documento; es la fuente de espacio menos costosa |
| 2 | **Acotar** los estilos a la lista semanal con una clase de página | `base.html` lo comparten 4 reportes: un cambio global los habría redimensionado a todos |
| 3 | El logo se **escala**, no se recorta | La imagen usa `object-fit: contain`, así que reducir la caja mantiene la proporción |
| 4 | El **espacio para firmar es intocable**: 60px de hueco (1.8 cm en papel) | Firmar no es opcional; es lo primero que se sacrificó al agrandar la letra y hubo que revertirlo |
| 5 | El **aire de fila vuelve a 3px** (el original) | Con 4px las firmas pierden su espacio. Con la letra en 8.5pt las filas ya quedan más altas que antes (+9 %), así que la legibilidad no se pierde |

**Orden de prioridad del presupuesto de espacio:** 1) legibilidad de la letra · 2) espacio
para firmar · 3) aire extra entre filas. El documento solo da para dos de los tres.

## Requisitos

- **R1** — La letra de la tabla sube de 7.5pt a 8.5pt; el encabezado de 7pt a 8pt; la columna
  DÍAS de 8pt a 9pt.
- **R2** — El aire entre filas deja **al menos 1.8 cm** de hueco en blanco sobre la línea de
  firma, medido sobre el papel.
- **R3** — El documento **sigue en una sola página** con la semana de 21 filas.
- **R4** — Ningún nombre se parte en dos líneas.
- **R5** — Los reportes de cobertura, carga de trabajo y lista de médicos **no cambian**.

## Criterios de aceptación

**AC1 — Un solo documento, un solo tamaño**
- **Dado** una semana con las 21 asignaciones posibles,
- **cuando** se exporta a PDF,
- **entonces** la salida tiene **1 página** y el contenido termina dentro del margen inferior.

**AC2 — Sin deformación**
- **Dado** el mismo contenido antes y después,
- **entonces** cada asignación sigue ocupando **una sola línea** (21 filas de asignación) y el
  número de líneas del documento no aumenta.

**AC3 — Los otros reportes no se tocan**
- **Dado** las plantillas de cobertura, carga de trabajo y lista de médicos,
- **entonces** su CSS emitido es **idéntico** al de antes del cambio (cero diferencias de reglas).

**AC4 — El contrato se mantiene**
- **Dado** el endpoint de exportación semanal,
- **entonces** sigue respondiendo `application/pdf` en 1 página con el permiso `export_reports`.

**AC5 — Hay dónde firmar**
- **Dado** el documento impreso,
- **cuando** se mira el bloque de firmas,
- **entonces** queda **al menos 1.8 cm de espacio en blanco** entre la última fila de la tabla y
  la línea de firma.

## Contrato

No cambia el contrato HTTP ni el payload. Se agregan **dos bloques de Jinja** a `base.html`
(`extra_styles` en el `<head>` y `page_class` en el contenedor `.page`), cuya implementación por
defecto es vacía. Solo `weekly_schedule.html` los sobrescribe.

## Impacto en tests

| Archivo | Efecto |
|---|---|
| `backend/tests/reports/test_week_report_service.py` | **Nuevo**: `test_weekly_sizing_is_scoped_and_does_not_leak_to_other_reports` — fija las 6 reglas y verifica que ninguno de los tres reportes hermanos sobrescriba los bloques |
| Resto de `tests/reports` | Sin cambios: **81 passed** |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Una cuarta área de servicio subiría el máximo a 28 filas y rompería la página | El cambio no empeora el margen (lo mejora); aun así, si se agrega un área hay que rehacer esta medición |
| Alguien agregue una regla sin acotar en `base.html` | Hay un test que lo detecta |
| Las firmas quedan más cerca de la tabla | Es el intercambio aceptado: a cambio entra la letra más grande |

## Resultado medido

Medido sobre el PDF real del endpoint, con la semana aprobada de 21 asignaciones. El hueco de
firma se mide siempre con el mismo método (última fila de la tabla → primer texto de la firma).

| Medida | Original | 1ª versión (corregida) | **Final** |
|---|---|---|---|
| Letra de la tabla | 7.5pt | 8.5pt | **8.5pt** |
| Encabezado | 7pt | 8pt | **8pt** |
| Columna DÍAS | 8pt | 9pt | **9pt** |
| Aire por fila | 3px | 4px | 3px |
| Logo | 128px | 96px | 96px |
| **Hueco de firma** | **2.09 cm** | 0.21 cm ❌ | **1.83 cm** |
| Páginas | 1 | 1 | **1** |
| Fin del contenido | 546.1 pt | 544.5 pt | **543.0 pt** |

La primera versión se pasó de agresiva con el hueco de firmas (70px → 20px): dejaba 2 mm sobre
el papel y no había dónde firmar. Corregido a 60px, que devuelve el 87 % del espacio original.

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Feedback | Sube la letra de la lista semanal y documenta la restricción de las 21 filas. El espacio se recupera del logo y del hueco de firmas, con los estilos acotados para no afectar a los otros tres reportes que comparten `base.html`. |
| 1.1.0 | 2026-10-09 | — | Feedback | **Corrección**: reducir el hueco de firmas a 20px dejó el documento sin espacio para firmar (0.21 cm). Se sube a 60px (1.83 cm, el 87 % del original) y el aire de fila vuelve a 3px para pagarlo. Se fija el orden de prioridad: legibilidad → espacio para firmar → aire extra entre filas. |
