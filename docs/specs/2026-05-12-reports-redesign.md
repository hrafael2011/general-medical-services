---
spec: reports-redesign
version: 1.0.0
status: accepted
created: 2026-05-12
updated: 2026-05-12
---

# Spec — Rediseño de Reportes y Eliminación de Import

## Goal

Reemplazar el módulo de reportes actual por uno profesional con filtros combinables, métricas accionables y exportación PDF/Excel. Eliminar el módulo de importación legacy por innecesario. Agregar gestión básica de usuarios para el administrador.

---

## Roles y Visibilidad

| Sección | Médico | Encargado | Administrador |
|---|---|---|---|
| Calendario | ver | ver | ver |
| Médicos | ver | ver | ver |
| Misiones | ver | ver | ver |
| Notificaciones | ver | ver | ver |
| Telegram | ver | ver | ver |
| Reportes | — | ver | ver |
| Auditoría | — | — | ver |
| Usuarios | — | — | ver (crear + resetear contraseña) |

---

## Módulo Import — Eliminación Completa

### Archivos a eliminar

| Archivo | Tipo |
|---|---|
| `backend/app/api/routes/import_staging.py` | Ruta API |
| `backend/app/application/import_pipeline/pipeline_service.py` | Servicio |
| `backend/app/application/import_pipeline/extractor.py` | Extractor |
| `backend/app/application/import_pipeline/normalizer.py` | Normalizador |
| `backend/app/application/import_pipeline/identity_resolver.py` | Resolvedor de identidad |
| `backend/app/application/import_pipeline/review_service.py` | Servicio de revisión |
| `backend/app/infrastructure/db/models/import_staging.py` | Modelos DB |
| `backend/app/infrastructure/repositories/import_staging.py` | Repositorio |
| `backend/app/schemas/import_staging.py` | Schemas Pydantic |
| `backend/tests/import_pipeline/test_pipeline_service.py` | Tests |
| `backend/tests/import_pipeline/test_normalizer.py` | Tests |
| `backend/tests/import_pipeline/test_review_service.py` | Tests |
| `frontend/src/api/import_staging.ts` | API client |
| `frontend/src/features/import/ImportView.tsx` | Componente |
| `frontend/src/features/import/ImportView.test.tsx` | Tests |
| `docs/specs/07-importacion-legacy.md` | Spec obsoleto |

### Ajustes colaterales

- `backend/app/api/router.py`: quitar `include_router(import_router)`
- `frontend/src/App.tsx`: quitar ruta `/import`
- `frontend/src/components/Sidebar.tsx`: eliminar grupo "DATOS" (Reportes + Importar)
- Nueva migración: `DROP TABLE import_staged_records, import_raw_extractions, import_source_files`

### Conservar del módulo actual

- Infraestructura `reportlab` y `pdf_templates.py` (se extienden)
- `backend/app/static/logo.png`
- Endpoints: `GET /reports/calendar/{id}/excel`, `GET /reports/doctor-history/excel`, `GET /reports/weekly-schedule`

### Eliminar del módulo actual de reportes

- 5 generadores PDF sin ruta HTTP: `generate_calendar_pdf`, `generate_doctor_history_pdf`, `generate_operational_summary_pdf`, `generate_mission_ranking_pdf`, `generate_doctor_list_pdf`
- Endpoints JSON: `GET /reports/notifications-summary`, `GET /reports/operational-summary`
- `frontend/src/features/reports/ReportsView.tsx` actual
- `frontend/src/api/reports.ts` actual

---

## Navegación

```
Sidebar:
┌──────────────┐
│ Calendario   │ ← Médico, Encargado, Admin
│ Médicos      │ ← Médico, Encargado, Admin
│ Misiones     │ ← Médico, Encargado, Admin
│ Notificaciones│← Médico, Encargado, Admin
│ Telegram     │ ← Médico, Encargado, Admin
│──────────────│
│ Reportes     │ ← Encargado, Admin
│──────────────│
│ Auditoría    │ ← Solo Admin
│ Usuarios     │ ← Solo Admin
└──────────────┘
```

---

## Reporte #1 — Cobertura y Brechas

**Objetivo:** Detectar áreas sin médico asignado en un período. Seguridad operacional.

### Filtros

- Período: mes/año inicio → mes/año fin
- Área de servicio: todas / emergencia / pista / disponible
- Rango militar: todos / General / Coronel / ...
- Sexo: todos / M / F
- Departamento: todos / específico

### Tarjetas de resumen

- % Cobertura general del período
- Total de brechas detectadas (días sin médico)
- Área más crítica (la que más brechas tuvo)
- Día de la semana más débil (con más faltas)

### Tabla principal — Cobertura por área

| Área | Días cubiertos | Días descubiertos | % Cobertura |
|---|---|---|---|

Cada fila expandible → días específicos que fallaron y quiénes estaban asignados los demás días.

### Tabla secundaria — Brechas por día (al expandir área)

| Fecha | Día | Área sin médico | Alternativa |
|---|---|---|---|

### Exportación

- PDF A4 horizontal con encabezado institucional FARD, filtros aplicados visibles, fecha de generación, bloque de firma
- Excel con misma estructura de datos

### Endpoint

```
GET /reports/coverage
  ?year_start=2026&month_start=1
  &year_end=2026&month_end=1
  &area=emergencia           (opcional)
  &rank=general              (opcional)
  &sex=M                     (opcional)
  &department_id=X           (opcional)
  &format=pdf                (opcional, default json)
```

---

## Reporte #2 — Carga de Trabajo

**Objetivo:** Reporte institucional de distribución de servicios. Presentable a dirección.

### Filtros

- Período: mes/año
- Área de servicio: todas / específica
- Rango militar: todos / específico
- Sexo: todos / específico
- Departamento: todos / específico
- Agrupar por: área / rango / departamento / sin agrupación
- Ordenar por: total de servicios (desc) / alfabético / rango

### Tarjetas de resumen

- Total de servicios en el período
- Médicos activos
- Promedio de servicios por médico
- Médico con más carga
- Médico con menos carga

### Gráfica

Barras horizontales con top N médicos por carga, coloreadas por área de servicio. Visible antes de la tabla como resumen visual.

### Tabla principal — Carga por médico

| Médico | Rango | Sexo | Depto | Emergencia | Pista | Disponible | Total |
|---|---|---|---|---|---|---|---|

Cada fila expandible → detalle de días específicos en que sirvió.

### Exportación

- PDF A4 horizontal con gráfica embebida, encabezado FARD, filtros visibles, bloque de firma
- Excel con misma estructura

### Endpoint

```
GET /reports/workload
  ?year=2026&month=1
  &area=emergencia           (opcional)
  &rank=general              (opcional)
  &sex=F                     (opcional)
  &department_id=X           (opcional)
  &group_by=area|rank|department|none
  &order_by=total_desc|alpha|rank
  &format=pdf                (opcional)
```

---

## Reporte #3 — Ficha Individual del Médico

**Objetivo:** Documento PDF formal con el expediente completo de un médico en un rango de fechas. Para auditorías, revisiones y reuniones.

### Selectores

- Médico: búsqueda por nombre (autocomplete)
- Desde: fecha (dd/mm/aaaa)
- Hasta: fecha (dd/mm/aaaa)

Si no se especifica rango de fechas, se usa todo el historial disponible.

### Vista previa en pantalla

Resumen compacto con los mismos bloques del PDF para confirmar antes de imprimir.

### Contenido del PDF (A4 vertical)

```
┌──────────────────────────────────────────┐
│  ESCUDO   FARD - Hospital Militar        │
│           Universitario Docente          │
│                                          │
│  FICHA DE SERVICIO MÉDICO               │
│  Generado: dd/mm/aaaa                    │
│                                          │
│  ─────────────────────────────────────   │
│  DATOS DEL MÉDICO                        │
│  ─────────────────────────────────────   │
│  Nombre, Rango, Sexo, Cédula,           │
│  Departamento, Áreas habilitadas         │
│                                          │
│  ─────────────────────────────────────   │
│  RESUMEN DEL PERÍODO (dd/mm/aa - dd/mm/aa)│
│  ─────────────────────────────────────   │
│  Total servicios, por área,              │
│  promedio semanal                        │
│                                          │
│  ─────────────────────────────────────   │
│  DETALLE DE SERVICIOS                    │
│  ─────────────────────────────────────   │
│  Fecha | Día | Área                     │
│                                          │
│  ─────────────────────────────────────   │
│  MISIONES EN EL PERÍODO                  │
│  ─────────────────────────────────────   │
│  Misión | Rol | Estado                  │
│                                          │
│  ─────────────────────────────────────   │
│  RESTRICCIONES Y LICENCIAS               │
│  ─────────────────────────────────────   │
│  Tipo | Fecha | Motivo                  │
│                                          │
│  ─────────────────────────────────────   │
│  DISPONIBILIDAD DECLARADA                │
│  ─────────────────────────────────────   │
│  Días de la semana                       │
│                                          │
│  ────  FIRMA ────      ────  SELLO ──── │
└──────────────────────────────────────────┘
```

### Endpoint

```
GET /reports/doctor-dossier/{doctor_id}
  ?date_from=2026-01-01       (opcional)
  &date_to=2026-12-31         (opcional)
  &format=pdf
```

---

## Endpoints Finales

```
GET /reports/coverage              ← NUEVO
GET /reports/workload              ← NUEVO
GET /reports/doctor-dossier/{id}   ← NUEVO
GET /reports/calendar/{id}/excel   ← conservado
GET /reports/doctor-history/excel  ← conservado
GET /reports/weekly-schedule       ← conservado
```

---

## Arquitectura Backend

```
backend/app/api/routes/reports.py          ← reescrito: 6 endpoints
backend/app/application/reports/
  report_service.py                         ← reescrito: métodos de reportes
  pdf_templates.py                          ← extendido: nuevas plantillas PDF
backend/app/schemas/reports.py              ← nuevo: schemas de filtros y respuestas
```

---

## Arquitectura Frontend

```
frontend/src/features/reports/
  ReportsView.tsx              ← reescrito: contenedor con tabs
  CoverageReport.tsx           ← NUEVO: reporte #1
  WorkloadReport.tsx           ← NUEVO: reporte #2
  DoctorDossierReport.tsx      ← NUEVO: reporte #3
frontend/src/api/reports.ts    ← reescrito: métodos nuevos
frontend/src/components/
  ReportFilters.tsx            ← NUEVO: filtros compartidos
  ReportSummaryCards.tsx       ← NUEVO: tarjetas de resumen reutilizables
```

`ReportsView` muestra 3 tabs: Cobertura, Carga de Trabajo, Ficha Individual. Cada tab carga su componente con sus filtros específicos.

---

## Gestión de Usuarios (solo Admin)

Navegación visible únicamente para `role == admin`.

```
GET    /users                    ← listar usuarios
POST   /users                    ← crear usuario
PATCH  /users/{id}/password      ← resetear contraseña
```

Componente `UsersView` con tabla de usuarios, modal de creación y acción de resetear contraseña.

---

## Auditoría (solo Admin)

Navegación visible únicamente para `role == admin`. Alcance y diseño a definir en spec separado. Este spec solo establece el requisito de visibilidad.

---

## Acceptance Criteria

1. El módulo Import queda completamente eliminado del código, rutas, navegación y base de datos.
2. El grupo "DATOS" desaparece del Sidebar.
3. "Reportes" aparece como sección propia visible solo para Encargado y Administrador.
4. El reporte de Cobertura muestra brechas por área con todos los filtros combinables y exporta a PDF y Excel.
5. El reporte de Carga de Trabajo muestra distribución con gráfica, filtros, agrupación y exporta a PDF y Excel.
6. El reporte de Ficha Individual genera un PDF formal con todos los bloques especificados para un rango de fechas.
7. "Usuarios" aparece en el Sidebar solo para Administrador, con capacidad de listar, crear y resetear contraseñas.
8. "Auditoría" aparece en el Sidebar solo para Administrador.
9. Los endpoints de reportes conservados (`/calendar/{id}/excel`, `/doctor-history/excel`, `/weekly-schedule`) siguen funcionando.
10. Los generadores PDF sin ruta y los endpoints JSON obsoletos quedan eliminados.

---

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.0.0 | 2026-05-12 | — | Inicial | Rediseño completo de reportes con 3 nuevos reportes, eliminación del módulo Import, roles de visibilidad, gestión de usuarios para admin. |
