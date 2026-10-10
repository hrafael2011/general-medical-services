---
spec: firmas-dinamicas-lista-semanal
version: 1.1.0
status: implementado
created: 2026-10-09
updated: 2026-10-09
---

# Spec — Firmas dinámicas y editables en la lista semanal

## Goal

Que las dos firmas de la lista semanal en PDF dejen de ser texto fijo en el código:

- **Izquierda** — el nombre del **usuario logueado que exporta** el documento (un encargado).
- **Derecha** — **editable** desde el sistema, porque cambia según quién esté en el puesto.

**Tareas de implementación:** [2026-10-09-firmas-dinamicas-lista-semanal-tasks.md](2026-10-09-firmas-dinamicas-lista-semanal-tasks.md)

## Contexto

Origen: pedido directo del usuario (2026-10-09). Hoy las dos firmas son constantes
(`DEFAULT_SIGNATURES` en `weasyprint_gen.py:42`) y solo cambian editando el código.

### Lo que ya existe (verificado)

| Pieza | Estado |
|---|---|
| Tabla `system_settings` (key/value) | ✅ existe |
| `ReportService._load_signatures()` lee 8 claves `pdf.sig_*` | ✅ existe, con fallback a los defaults |
| Repositorio `get_setting` / `upsert_setting` | ✅ existe |
| Las 8 claves sembradas en la base | ❌ **no existen** — por eso salen fijas |
| Endpoint para leer o escribir `system_settings` | ❌ **ninguno** |
| UI de configuración | ❌ **ninguna** |
| Títulos/rango en `users` | ❌ no existen (`name`, `email`, `role`, `permissions`) |

> El mecanismo estaba construido a medias: se lee de la base, pero nunca se sembró y no hay
> forma de escribir. Esta spec lo cierra, solo para la lista semanal.

## Alcance

| Dentro | Fuera |
|---|---|
| PDF de la lista semanal | Cobertura, carga de trabajo, ficha del médico y lista de médicos |
| Firma izquierda: nombre automático del usuario logueado | El PDF del calendario completo (no imprime firmas) |
| Títulos izquierdos y firma derecha completos: editables | Los otros 4 generadores de PDF |
| Una pestaña nueva en la pantalla de Catálogos | Migraciones de base de datos |

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | La izquierda sale del **usuario que exporta**, no del dueño del calendario | Es quien firma el documento que saca; el endpoint ya recibe ese usuario y hoy lo ignora |
| 2 | Los **3 títulos de la izquierda son editables** | Si mañana firma alguien con otro rango, un título fijo estaría mintiendo |
| 3 | La derecha completa (**nombre + 3 títulos**) es editable | Cambia según la persona esté o no en el puesto |
| 4 | **Una sola pantalla**: pestaña nueva en `CatalogsPage` | `CatalogsPage` ya es una página con pestañas; no se crea pantalla nueva |
| 5 | Los valores viven en `system_settings` con claves `pdf.sig_*` | El mecanismo de lectura ya existe; no hace falta tabla nueva ni migración |
| 6 | **Sin override del nombre izquierdo** | Pedido explícito de simplicidad: el nombre es el del usuario; si está mal escrito, se corrige en Usuarios |

## Requisitos

- **R1** — La firma izquierda muestra el `name` del usuario autenticado que pidió el PDF.
- **R2** — Si no hay usuario (exportación por Telegram), la izquierda usa el valor guardado en
  `pdf.sig_left_name`, y si tampoco existe, el default actual.
- **R3** — Los 3 títulos de la izquierda se leen de `pdf.sig_left_title1..3`.
- **R4** — La derecha (`pdf.sig_right_name` + `pdf.sig_right_title1..3`) es editable.
- **R5** — Una pestaña **Firmas** en Catálogos permite ver y guardar esos 7 textos.
- **R6** — La pestaña indica claramente que el nombre de la izquierda **no se edita ahí**, porque
  sale del usuario que exporta.
- **R7** — Sin migraciones. Los valores ausentes caen a los defaults actuales.
- **R8** — Los otros 4 PDFs que firman **no cambian**.

## Criterios de aceptación

**AC1 — La izquierda es quien exporta**
- **Dado** que Alexandra (encargado) exporta la semana,
- **entonces** la firma izquierda lleva **su** nombre, y el mismo documento exportado por otro
  encargado lleva el de ese otro.

**AC2 — Los títulos se editan**
- **Dado** el formulario de Firmas con los títulos de la izquierda,
- **cuando** se cambian y se guardan,
- **entonces** el siguiente PDF sale con los títulos nuevos y **sin tocar código**.

**AC3 — La derecha se edita**
- **Dado** el formulario con nombre y títulos de la derecha,
- **cuando** se dejan vacíos,
- **entonces** el bloque derecho sale sin texto, pero el documento sigue en 1 página.

**AC4 — Una sola pantalla**
- **Dado** el panel de administración,
- **entonces** las dos firmas se editan en **la misma pestaña**, sin pantallas adicionales.

**AC5 — Sin usuario no se rompe**
- **Dado** una exportación sin usuario autenticado (Telegram),
- **entonces** la izquierda cae al valor por defecto y el PDF se genera igual.

**AC6 — Nada más cambia**
- **Dados** cobertura, carga de trabajo, ficha y lista de médicos,
- **entonces** siguen imprimiendo exactamente las firmas de hoy.

## Contrato

Dos endpoints nuevos en el router de catálogos (permiso `manage_catalogs`):

```
GET /api/catalogs/report-signatures
{
  "left_title1": "Sargento Médico FARD.",
  "left_title2": "Encargada de los Servicios de los Médicos Generales",
  "left_title3": "del Hosp. Mil. Univ. Doc. FARD, \"DRL\".",
  "right_name": "ING. CARLOS J. ENCARNACION GONZALEZ",
  "right_title1": "1er Tt. Ingeniero en Sistema FARD.",
  "right_title2": "Encargado del Departamento Administrativo de la",
  "right_title3": "Sub Dirección de Recursos Humanos del Hosp. Mil. Univ. Doc. FARD, \"DRL\"."
}

PUT /api/catalogs/report-signatures   (los mismos 7 campos, todos requeridos)
→ 200 con el estado guardado
```

**No se envía ni se edita el nombre de la izquierda**: sale del usuario autenticado.

El `GET` devuelve los defaults actuales cuando las claves no están en la base, así que **no hace
falta sembrar nada** y la pantalla nunca aparece vacía en la primera visita.

## Impacto en tests

| Archivo | Efecto |
|---|---|
| `backend/tests/reports/test_week_report_service.py` | La firma izquierda pasa a depender del usuario: hay que cubrir usuario presente y ausente |
| `backend/tests/reports/test_report_service.py` | `_load_signatures` mantiene su comportamiento de fallback |
| `backend/tests/catalogs/` | Tests de los dos endpoints nuevos (leer con defaults, guardar, permisos) |
| `frontend/src/features/catalogs/CatalogsPage.test.tsx` | Pestaña nueva |
| Resto de `tests/reports` | Sin cambios: los otros 4 generadores no se tocan |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El `name` del usuario no está en formato de firma (`"Alexandra"`, `"Encargado Pruebas"`) | No se resuelve con código: se corrige en el perfil del usuario. Queda documentado y avisado |
| Un admin exporta y firma con el título de encargada | Es el comportamiento pedido (firma quien exporta). Si molesta, se decide después |
| La derecha vacía deja el bloque en blanco | AC3 lo cubre: el documento sigue siendo válido |
| Alguien edita los títulos y afecta a otros reportes | No puede: solo la lista semanal lee esas claves |

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Nuevo requerimiento | Las firmas de la lista semanal dejan de ser constantes: la izquierda sale del usuario que exporta y los títulos izquierdos más la firma derecha pasan a ser editables desde una pestaña nueva en Catálogos. Se documenta que el mecanismo de `system_settings` ya existía pero nunca se sembró ni se expuso. |
| 1.1.0 | 2026-10-09 | — | Implementación | Estado pasa a `implementado`. Dos endpoints en el router de catálogos (permiso `manage_catalogs`), el `signer_name` recorre la cadena hasta `_load_signatures`, y una pestaña **Firmas** en `CatalogsPage`. Verificado con el PDF real: exportado por un encargado firma "Rafael Hendrick" y por un admin firma "Administrador", mientras cobertura conserva su firma fija. Sin migraciones. |
