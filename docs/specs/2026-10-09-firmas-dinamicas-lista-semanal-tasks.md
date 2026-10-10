# Tasks — Firmas dinámicas y editables en la lista semanal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-firmas-dinamicas-lista-semanal.md](2026-10-09-firmas-dinamicas-lista-semanal.md)

**Goal:** Que la firma izquierda de la lista semanal sea el usuario logueado que exporta, y que
los títulos izquierdos más la firma derecha completa se editen desde una pestaña en Catálogos.

**Architecture:** Los textos viven en `system_settings` con las claves `pdf.sig_*` que
`ReportService._load_signatures()` ya sabe leer. Se agregan dos endpoints en el router de
catálogos y una pestaña en la pantalla de Catálogos. El nombre de la izquierda **no se guarda**:
viaja desde el endpoint de exportación, que ya recibe el usuario autenticado y hoy lo descarta,
hacia `build_weekly_schedule` y de ahí al generador.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Jinja2, WeasyPrint, React + TanStack Query, pytest

**Estado:** ✅ **Implementado** en la rama `feat/whatsapp-pdf-semanal` (2026-10-09).

**Evidencia de verificación:**

| Comprobación | Cómo | Resultado |
|---|---|---|
| La izquierda es quien exporta | PDF exportado por *Rafael Hendrick* (encargado) | firma izquierda = **"Rafael Hendrick"** |
| Cambia según el usuario | el mismo PDF exportado por *Administrador* | firma izquierda = **"Administrador"** |
| Los títulos se editan | `PUT` cambiando un título + reexportar | el PDF sale con el título nuevo |
| `GET` sin nada guardado | `curl` en vivo | devuelve los 7 defaults (**no hace falta sembrar**) |
| Permisos | encargado sin `manage_catalogs` | **403** en GET y PUT |
| Sin usuario (Telegram) | `build_weekly_schedule()` sin `signer_name` | cae al valor por defecto |
| Los otros reportes no cambian | PDF de **cobertura** exportado por el admin | sigue con **"Dra. MIGUELINA A. ACOSTA RAMOS"** ✅ |
| Tests backend | `pytest backend/tests -q` desde la raíz | **1789 passed**, 0 fallos |
| Tests frontend | `vitest run` | **115 passed** |
| Lint | `ruff` / `eslint` | backend: 19 errores baseline → **18** (cero nuevos) · frontend limpio |

---

## Fase 1 — Backend: los dos endpoints

### Task 1.1 — Schemas

**Archivo:** `backend/app/schemas/catalogs.py`

- [x] **Añadir** `ReportSignaturesRead` y `ReportSignaturesUpdate` con los 7 campos editables:
      `left_title1`, `left_title2`, `left_title3`, `right_name`, `right_title1`,
      `right_title2`, `right_title3`.
- [x] **No incluir** el nombre de la izquierda: sale del usuario autenticado.

### Task 1.2 — Service

**Archivo:** `backend/app/application/catalogs/service.py`

- [x] **Añadir** `get_report_signatures()`: lee las 7 claves y **cae a `DEFAULT_SIGNATURES`**
      cuando no existen. Así la pantalla nunca aparece vacía y no hace falta sembrar nada.
- [x] **Añadir** `save_report_signatures(payload)`: `upsert_setting` de las 7 claves con
      `updated_at` y una descripción por clave, en el mismo estilo del seed existente.

### Task 1.3 — Rutas

**Archivo:** `backend/app/api/routes/catalogs.py`

- [x] **Añadir** `GET /api/catalogs/report-signatures` con `require_permission("manage_catalogs")`.
- [x] **Añadir** `PUT /api/catalogs/report-signatures` con el mismo permiso y `session.commit()`.

> El router ya tiene `prefix="/catalogs"`, así que las rutas quedan bajo `/api/catalogs/...`.

---

## Fase 2 — Backend: la izquierda es quien exporta

### Task 2.1 — Aceptar el firmante en el generador

**Archivo:** `backend/app/application/reports/report_service.py`

- [x] **Modificar** `_load_signatures(signer_name: str | None = None)`: si viene `signer_name`,
      `left_name` es ese valor; si no, la clave `pdf.sig_left_name` y, en último caso, el default.
- [x] **Propagar** el parámetro en `build_weekly_schedule(..., signer_name: str | None = None)`.

> `_load_signatures()` es el único punto que arma el `SignatureConfig`, así que el cambio queda
> en un solo sitio.

### Task 2.2 — Pasar el usuario desde la ruta

**Archivo:** `backend/app/api/routes/reports.py` (`export_weekly_list_pdf`, ≈ línea 184)

- [x] **Renombrar** `_current_user` a `current_user` (hoy se recibe y se ignora).
- [x] **Pasar** `signer_name=current_user.name` a `service.build_weekly_schedule(...)`.

> El endpoint ya exige el permiso `export_reports`, así que el usuario siempre está disponible
> cuando se exporta desde el panel. Sin usuario (Telegram) se usa el fallback de R2.

### Task 2.3 — Confirmar que los otros 4 no cambian

- [x] **Verificar** que `generate_coverage_pdf`, `generate_workload_pdf`, `generate_dossier_pdf`
      y `generate_doctor_list_pdf` siguen llamando a `_signature_context()` igual que hoy.

---

## Fase 3 — Frontend: la pestaña Firmas

### Task 3.1 — Cliente de API

**Archivo:** `frontend/src/api/doctors.ts` (ahí viven las llamadas de catálogos)

- [x] **Añadir** `getReportSignatures()` y `saveReportSignatures(payload)`.

### Task 3.2 — Pestaña en Catálogos

**Archivo:** `frontend/src/features/catalogs/CatalogsPage.tsx`

- [x] **Añadir** `"signatures"` al tipo `Tab` y una entrada en `TABS` con la etiqueta **Firmas**.
- [x] **Añadir** el componente `SignaturesTab` con un campo de texto por cada uno de los 7 valores.
- [x] **Mostrar** de forma visible que el nombre de la izquierda **no se edita ahí**, porque es el
      usuario que exporta (R6 / AC4).
- [x] **Guardar** con `useMutation` + toast de éxito/error, siguiendo el patrón de las otras
      pestañas.

**Cómo debe verse la pestaña:**

```
  [ Rangos ]  [ Departamentos ]  [ Motivos ]  [ Firmas ]

  ┌─ Firma izquierda ─────────────────────────────────────────┐
  │  Nombre:  (se toma del usuario que exporta el documento)  │
  │  Título 1: [ Sargento Médico FARD.                      ] │
  │  Título 2: [ Encargada de los Servicios de los Médicos… ] │
  │  Título 3: [ del Hosp. Mil. Univ. Doc. FARD, "DRL".     ] │
  └───────────────────────────────────────────────────────────┘

  ┌─ Firma derecha ───────────────────────────────────────────┐
  │  Nombre:   [ ING. CARLOS J. ENCARNACION GONZALEZ        ] │
  │  Título 1: [ 1er Tt. Ingeniero en Sistema FARD.         ] │
  │  Título 2: [ Encargado del Departamento Administrativo… ] │
  │  Título 3: [ Sub Dirección de Recursos Humanos del…     ] │
  └───────────────────────────────────────────────────────────┘
                                        [ Guardar firmas ]
```

---

## Fase 4 — Tests

### Task 4.1 — Endpoints

- [x] **Test** `GET` devuelve los defaults cuando las claves no existen en la base.
- [x] **Test** `PUT` guarda y un `GET` posterior devuelve lo guardado.
- [x] **Test** ambos responden `403` sin el permiso `manage_catalogs`.

### Task 4.2 — La izquierda dinámica

- [x] **Test** `build_weekly_schedule(signer_name="Alexandra")` produce una firma izquierda con
      ese nombre.
- [x] **Test** sin `signer_name` cae al valor por defecto (AC5).
- [x] **Test** los títulos guardados en `system_settings` llegan al `SignatureConfig`.

### Task 4.3 — Frontend

- [x] **Test** la pestaña **Firmas** existe y muestra los 7 campos.
- [x] **Test** guardar llama al endpoint con el payload correcto.

---

## Fase 5 — Verificación en el documento

### Task 5.1 — Dos usuarios, dos firmas

- [x] **Exportar** la misma semana con dos usuarios distintos y confirmar que cambia solo el
      nombre de la izquierda.

### Task 5.2 — Editar y ver el efecto

- [x] **Cambiar** un título desde la pantalla y confirmar que el siguiente PDF lo refleja sin
      tocar código.

### Task 5.3 — No romper lo que ya está

- [x] **Confirmar** que el documento sigue en **1 página** con las 21 filas y que el hueco de
      firma se mantiene.
- [x] **Confirmar** que cobertura, carga de trabajo, ficha y lista de médicos siguen igual.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué resuelve | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 1 | Fase 1 | Poder leer y guardar las firmas | Bajo | ✅ hecho |
| 🔴 2 | Fase 2 | La izquierda es quien exporta | Medio — toca la cadena de llamadas | ✅ hecho |
| 🟠 3 | Fase 3 | La pantalla para editarlas | Bajo | ✅ hecho |
| 🟠 4 | Fase 4 | Cobertura | Bajo | ✅ hecho |
| 🟡 5 | Fase 5 | Verificación en el papel | Bajo | ✅ hecho |

## Archivos a tocar

| Archivo | Tipo |
|---|---|
| `backend/app/schemas/catalogs.py` | modificar — 2 schemas |
| `backend/app/application/catalogs/service.py` | modificar — leer y guardar |
| `backend/app/api/routes/catalogs.py` | modificar — 2 endpoints |
| `backend/app/application/reports/report_service.py` | modificar — firmante en la cadena |
| `backend/app/api/routes/reports.py` | modificar — pasar el usuario |
| `frontend/src/api/doctors.ts` | modificar — 2 funciones |
| `frontend/src/features/catalogs/CatalogsPage.tsx` | modificar — pestaña Firmas |
| Tests backend y frontend | añadir |

**Sin migraciones.**

## Casillas abiertas

1. **Revisión visual del usuario** en el navegador — la pestaña **Firmas** está en Catálogos, y la
   exportación ya firma con el usuario logueado. Los datos están verificados por API y tests;
   falta su visto bueno en pantalla.
2. **Nombres de usuario en formato de firma** (`"Alexandra"`, `"Encargado Pruebas"`) — hay que
   corregirlos en la pantalla de Usuarios para que el papel se vea bien. **No es código**: queda
   como tarea de datos del usuario.
3. **Merge a `master`** — pendiente de autorización. Van tres commits en la rama.

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas tras confirmar el diseño con el usuario. Sin implementar. |
| 2026-10-09 | 1.1–1.3 | Schemas, `get_report_signatures`/`save_report_signatures` y los endpoints `GET`/`PUT`. Verificado en vivo: el `GET` devuelve los defaults sin sembrar nada. |
| 2026-10-09 | 2.1–2.3 | `signer_name` recorre la cadena; la ruta de exportación pasa `current_user.name`. Los otros 4 generadores siguen llamando a `_signature_context()` sin cambios. |
| 2026-10-09 | 3.1–3.2 | `ReportSignatures` + dos funciones en la API del frontend; pestaña **Firmas** en `CatalogsPage` con estilos en línea, siguiendo el patrón de las otras pestañas. |
| 2026-10-09 | 4.1–4.3 | 8 tests backend nuevos (defaults, round-trip, 403, firmante, fallback) y 2 de frontend. |
| 2026-10-09 | 5.1–5.3 | PDF real por dos usuarios distintos: izquierda = "Rafael Hendrick" vs "Administrador". Cobertura sigue con la firma fija. Suites: 1789 backend / 115 frontend, 0 fallos. |
