---
spec: tipografia-lista-semanal-pdf
version: 1.0.0
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
| 1 | Recuperar espacio del **logo** (128px → 96px) y del **hueco de firmas** (70px → 20px) | Son los dos elementos sobredimensionados para este documento; sin liberar ahí, ninguna letra más grande cabe |
| 2 | **Acotar** los estilos a la lista semanal con una clase de página | `base.html` lo comparten 4 reportes: un cambio global los habría redimensionado a todos |
| 3 | El logo se **escala**, no se recorta | La imagen usa `object-fit: contain`, así que reducir la caja mantiene la proporción |

## Requisitos

- **R1** — La letra de la tabla sube de 7.5pt a 8.5pt; el encabezado de 7pt a 8pt; la columna
  DÍAS de 8pt a 9pt.
- **R2** — El aire vertical de cada fila sube de 3px a 4px.
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

| Medida | Antes | Después |
|---|---|---|
| Letra de la tabla | 7.5pt | **8.5pt** |
| Encabezado | 7pt | **8pt** |
| Columna DÍAS | 8pt | **9pt** |
| Aire por fila | 3px | **4px** |
| Logo | 128px | 96px |
| Hueco de firmas | 70px | 20px |
| **Páginas** | 1 | **1** |
| **Fin del contenido** | 546.1 pt | **544.5 pt** (más holgura que antes) |

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Feedback | Sube la letra y el aire de las filas de la lista semanal. Se documenta la restricción de las 21 filas y que el espacio se recupera del logo y del hueco de firmas, con los estilos acotados para no afectar a los otros tres reportes que comparten `base.html`. |
