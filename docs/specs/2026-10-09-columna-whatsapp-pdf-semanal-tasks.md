# Tasks — Columna WHATSAPP / CEL en la lista semanal en PDF

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-columna-whatsapp-pdf-semanal.md](2026-10-09-columna-whatsapp-pdf-semanal.md)

**Goal:** Que la lista semanal exportada en PDF muestre el WhatsApp/celular de cada médico
asignado, con el relleno de la migración (`0000000000`) impreso en blanco.

**Architecture:** El dato ya existe en `doctors.whatsapp_phone` y ya se expone por la API. El
cambio vive **solo en la capa de reportes**: `ReportService.build_weekly_schedule` deja de
construir un mapa `id → nombre` y pasa a conservar el objeto del médico, para poder copiar su
teléfono al dict de cada asignación; la plantilla `weekly_schedule.html` gana la cuarta
columna. El PDF se sigue generando con WeasyPrint en A4 horizontal.

**Tech Stack:** Python 3.12, SQLAlchemy, WeasyPrint, Jinja2, pytest

**Estado:** ✅ **Implementado** en la rama `feat/whatsapp-pdf-semanal` (2026-10-09).
Autorización explícita del usuario obtenida antes de tocar código.

**Evidencia de verificación (2026-10-09) — la columna SÍ está implementada:**

| Comprobación | Comando | Resultado |
|---|---|---|
| Suite de reportes | `pytest tests/reports -q` | **80 passed** |
| Suite completa del backend | `pytest tests -q` | **1747 passed**, 0 fallos de código |
| Tests de raíz (CWD correcto) | `pytest backend/tests/test_*.py -q` | **44 passed** |
| Columna en la plantilla | `grep -c "WHATSAPP / CEL" weekly_schedule.html` | **1** |
| Render real del PDF | WeasyPrint + `pdftotext -layout` | Cabecera `WHATSAPP / CEL` y números en cada fila |
| Celda del relleno | muestra con `whatsapp_phone=""` | **Vacía**, sin `0000000000` |

---

## Fase 1 — Dato en el generador

**Impacto:** alto — sin esto la plantilla no tiene qué imprimir.

### Task 1.1 — Conservar el médico completo en el mapa

**Archivo:** `backend/app/application/reports/report_service.py`

- [x] **Reemplazar** el mapa de nombres:

```python
# ANTES
doctors = {d.id: d.name for d in self.doctor_repo.list_all()}

# DESPUÉS
doctors = {d.id: d for d in self.doctor_repo.list_all()}
```

- [x] **Añadir** la clave al dict de cada asignación:

```python
doctor = doctors.get(a.doctor_id)
day_assignments.setdefault(a.service_date, []).append({
    "rank_name": doctor.name if doctor else a.doctor_id,
    "whatsapp_phone": _clean_phone(getattr(doctor, "whatsapp_phone", None)),
    "location": areas.get(a.service_area_id, a.service_area_id),
    "_area_id": a.service_area_id,
})
```

> ⚠️ **Un solo mapa alimenta los dos caminos**: el semanal (`week_id`) y el mensual. El cambio
> aplica a ambos; no se duplicó lógica. El mensual no imprime la columna, así que la clave
> extra simplemente viaja sin usarse.

### Task 1.2 — Helper de limpieza del teléfono

**Archivo:** `backend/app/application/reports/report_service.py` (nivel de módulo)

- [x] **Añadir** el helper:

```python
_PHONE_PLACEHOLDER = "0000000000"


def _clean_phone(value: object) -> str:
    """Return a printable phone, or "" when there is nothing real to print."""
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    return "" if cleaned == _PHONE_PLACEHOLDER else cleaned
```

- [x] **Verificar** el helper: cubierto por `test_clean_phone_rejects_placeholder_and_non_strings`
      (`None`, `""`, `"   "`, `"0000000000"`, `MagicMock()` → `""`; número válido → tal cual).

---

## Fase 2 — Columna en la plantilla

### Task 2.1 — Cabecera y celdas

**Archivo:** `backend/app/application/reports/templates/weekly_schedule.html`

- [x] **Reajustar** los anchos y añadir la cabecera:

```html
<th style="width:14%;">DÍAS</th>
<th style="width:40%;">RANGO / NOMBRE</th>
<th style="width:18%;">WHATSAPP / CEL</th>
<th style="width:28%;">LUGAR SERV.</th>
```

- [x] **Añadir** la celda en el cuerpo:

```html
<td>{{ assgn.get("rank_name", "") }}</td>
<td>{{ assgn.get("whatsapp_phone", "") }}</td>
<td>{{ assgn.get("location", "") }}</td>
```

- [x] **No tocar** el `rowspan` del día, las clases `day-white` / `day-accent` ni el
      `day-divider` — el agrupamiento por día y las bandas alternadas quedaron igual.

### Task 2.2 — Comprobar el render real

- [x] **Generar** el PDF con nombres largos y confirmar que la cuarta columna entra sin cortar
      texto ni reducir la letra. Render de prueba con `MAY. ROSARIO, PEDRO ANTONIO` (el nombre
      más largo): la fila entra completa, sin partirse en dos líneas.
- [x] **Anchos confirmados**: `14 / 40 / 18 / 28` se mantienen. **No** hizo falta el ajuste de
      emergencia a `14 / 43 / 15 / 28`.

---

## Fase 3 — Tests

### Task 3.1 — Actualizar los mocks existentes

> Estos dos tests **renderizan la plantilla real** con WeasyPrint. Si el mock del médico no
> trae el atributo, `_clean_phone` lo descarta y la celda sale vacía — no falla, pero tampoco
> prueba nada.

- [x] `backend/tests/reports/test_report_service.py` — `mock_doc.whatsapp_phone = "809-555-1234"`.
- [x] `backend/tests/reports/test_week_report_service.py` — los dos mocks de médico llevan su
      teléfono, a través de un helper nuevo `_doctor(...)`.

> ### 🐛 Hallazgo: los mocks de médico nunca tuvieron nombre
>
> `MagicMock(id="doc1", name="LOPEZ, JUAN")` **no** crea un atributo `.name`: para `MagicMock`,
> `name=` es el nombre interno del mock. El resultado es que `doctor.name` devolvía **otro mock
> hijo**, y su `repr` viajaba al PDF. Los tests no lo detectaron porque solo asertaban que la
> salida empezara por `%PDF-` o que el payload fuera una lista.
>
> Se descubrió al añadir la primera aserción real sobre el contenido del payload. Corregido con
> el helper `_doctor(doctor_id, name, phone)`, que asigna el nombre **después** de construir el
> mock. De paso, `_clean_phone` rechaza valores que no sean `str`, así que un mock nunca más
> puede imprimirse en el documento.

### Task 3.2 — Test de la columna nueva

**Archivo:** `backend/tests/reports/test_week_report_service.py`

- [x] **Test AC1** — `test_weekly_schedule_payload_includes_whatsapp_phone`: el teléfono llega
      al payload, junto al nombre y el área.
- [x] **Test AC2** — `test_weekly_schedule_blanks_unusable_phone` (parametrizado con
      `"0000000000"`, `""`, `"   "`, `None`): todos producen `""`.
- [x] **Test del helper** — `test_clean_phone_rejects_placeholder_and_non_strings`.
- [x] **Test de la plantilla** — `test_weekly_template_renders_whatsapp_column`: renderiza
      `weekly_schedule.html` y aserta la cabecera nueva, el número, y que las tres columnas
      viejas sobreviven.

### Task 3.3 — Correr la suite

- [x] `cd backend && ./.venv/bin/python -m pytest tests/reports -q` → **80 passed**.
- [x] **Cero regresiones**: suite completa `1747 passed`. El único fallo
      (`test_migrations.py::test_alembic_has_single_head`) es de **CWD**: `alembic.ini` vive en
      la raíz del repo, y el test se corrió desde `backend/`. Desde la raíz pasa (**5 passed**).
      Se completaron los tests que quedaron sin correr: **44 passed**.

---

## Fase 4 — Verificación en el documento

### Task 4.1 — Render end-to-end

- [x] **Renderizar** el PDF real con el generador de producción (WeasyPrint + la plantilla del
      repo) y extraer el texto: la cabecera `WHATSAPP / CEL` aparece con un número por fila.
- [x] **Confirmar** que la fila con teléfono vacío sale en blanco, sin `0000000000`.
- [x] **Confirmar** que `DÍAS`, `RANGO / NOMBRE` y `LUGAR SERV.` siguen intactas, con el
      agrupamiento por día.
- [ ] **Pendiente — pulsar el botón en el panel en vivo** (requiere entorno levantado, sesión
      iniciada y una semana aprobada con datos reales). El camino está cubierto por tests y por
      el render directo; falta solo el click-through manual.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué arregla | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 1 | Fase 1 | El dato llega al payload de la plantilla | Bajo | ✅ hecho |
| 🔴 2 | Fase 2 | La columna existe y se ve | Bajo | ✅ hecho |
| 🟠 3 | Fase 3 | Cobertura y no-regresión | Bajo | ✅ hecho |
| 🟡 4 | Fase 4 | Verificación en el documento real | Bajo | ✅ render verificado · ⬜ click en el panel |

## Archivos tocados

| Archivo | Tipo |
|---|---|
| `backend/app/application/reports/report_service.py` | modificado — helper + payload |
| `backend/app/application/reports/templates/weekly_schedule.html` | modificado — 4ª columna |
| `backend/tests/reports/test_report_service.py` | modificado — mock con teléfono |
| `backend/tests/reports/test_week_report_service.py` | modificado — helper `_doctor` + 4 tests nuevos |

## Casillas abiertas

1. **Click-through en el panel en vivo** (Task 4.1) — verificación manual pendiente.
2. **Cuántas filas tienen `0000000000`** en producción (`[A VERIFICAR]`) — determina cuántos
   huecos verá el encargado en el papel. No se consultó la base de producción.
3. **Defecto preexistente en Telegram** (`tool_handlers.py:1116,1122`) — fuera de alcance,
   documentado en el spec. Merece su propio arreglo.
4. **Merge a `master`** — pendiente de autorización explícita.

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas. Sin implementar. |
| 2026-10-09 | Autorización | El usuario autoriza la implementación. |
| 2026-10-09 | 1.1 / 1.2 | Rama `feat/whatsapp-pdf-semanal`. Payload con `whatsapp_phone` + helper `_clean_phone`. |
| 2026-10-09 | 2.1 / 2.2 | Columna `WHATSAPP / CEL` en la plantilla. Render real sin recortes con nombres largos. |
| 2026-10-09 | 3.1 | Mocks corregidos. Hallazgo: `MagicMock(name=...)` no crea el atributo `.name`. |
| 2026-10-09 | 3.2 | 4 tests nuevos (AC1, AC2, helper y plantilla). |
| 2026-10-09 | 3.3 | `tests/reports`: 80 passed. Suite completa: 1747 passed sin fallos de código. |
| 2026-10-09 | 4.1 | Render real verificado por extracción de texto. Click en el panel, pendiente. |
