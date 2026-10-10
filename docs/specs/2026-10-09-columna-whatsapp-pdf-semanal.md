---
spec: columna-whatsapp-pdf-semanal
version: 1.1.0
status: implementado
created: 2026-10-09
updated: 2026-10-09
---

# Spec — Columna WHATSAPP / CEL en la lista semanal en PDF

## Goal

Que la **lista semanal** exportada en PDF desde el calendario muestre el WhatsApp/celular de
cada médico asignado, para que el encargado pueda contactarlo teniendo el documento en la
mano, sin volver al sistema.

**Tareas de implementación:** [2026-10-09-columna-whatsapp-pdf-semanal-tasks.md](2026-10-09-columna-whatsapp-pdf-semanal-tasks.md)

## Contexto

Origen: pedido directo del usuario (2026-10-09) — *"el reporte semanal que se imprime en PDF,
en calendario, quiero agregar el campo de su WhatsApp (celular) y que cuando se exporta a PDF
aparezca"*.

El documento se genera desde el botón **PDF** de cada semana **aprobada** en la pantalla del
calendario. Hoy el listado impreso cierra el ciclo operativo del encargado (quién está de
servicio cada día y en qué área), pero no le da forma de contactar a esa persona: el teléfono
existe en el sistema y **nunca llega al papel**.

### Estado verificado (2026-10-09)

| Qué | Dónde | Estado |
|---|---|---|
| Columnas del PDF semanal | `backend/app/application/reports/templates/weekly_schedule.html:17-19` | `DÍAS 18%` · `RANGO / NOMBRE 52%` · `LUGAR SERV. 30%` — **sin teléfono** |
| Teléfono en todas las plantillas de PDF | `backend/app/application/reports/templates/*.html` | **Cero coincidencias** (`whatsapp`/`phone`/`tel`) |
| Campo en base de datos | `backend/app/infrastructure/db/models/doctors.py:47` | `whatsapp_phone String(40) NOT NULL` — **ya existe** |
| Migraciones del campo | `20260524_0040` (lo crea), `20260527_0041` (reemplaza `phone`, backfill, `SET NOT NULL`) | **No hace falta migración nueva** |
| Exposición en API | `backend/app/schemas/doctors.py:18,40,66,89` · `frontend/src/api/doctors.ts:12,29,141` | Ya viaja al frontend |
| Edición del campo | `frontend/src/features/doctors/DoctorForm.tsx:21,132` | Ya editable |
| Relleno heredado de la migración | `20260527_0041` | Filas sin teléfono quedaron con `'0000000000'` |
| Camino del PDF | `CalendarGrid.tsx:560` → `reports.py:184` → `report_service.py:631,747` → `weasyprint_gen.py:114` → `weekly_schedule.html` | WeasyPrint, A4 horizontal (`base.html:79,109`) |
| Permiso del endpoint | `reports.py:188` | `export_reports` — sin cambios |

**Conclusión del hallazgo:** el dato existe de punta a punta; el único tramo que falta es
**el dict interno que alimenta la plantilla y la plantilla misma**. No hay trabajo de datos.

## Alcance

| Dentro | Fuera |
|---|---|
| PDF de la lista semanal (una semana concreta) | PDF del **calendario completo** (grilla mensual, `full_calendar.html`) |
| Filtro del valor de relleno `0000000000` | Pantalla del calendario (`CalendarGrid.tsx`) |
| Reajuste de los anchos de columna | Formulario de médicos (ya tiene el campo) |
| Test de la columna nueva | Migraciones, modelos, API pública, permisos |
| | Envío del PDF por Telegram/WhatsApp |

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | Un `whatsapp_phone` igual a `0000000000` (o vacío/espacios) se imprime **en blanco**, no como texto | Es el relleno que metió la migración `0041`; imprimirlo sería un número falso |
| 2 | Solo el **PDF semanal** | Es el documento que se usa en el día a día; la grilla mensual no tiene espacio por celda |
| 3 | El PDF sigue **solo descargándose** desde el panel | El usuario confirmó que ese es el alcance de exposición aceptado |

## Requisitos

- **R1** — El PDF semanal incluye una columna titulada **`WHATSAPP / CEL`**.
- **R2** — Cada fila de asignación muestra el `whatsapp_phone` del médico de esa fila.
- **R3** — Si el teléfono es el relleno de la migración (`0000000000`), o está vacío, la celda
  se imprime **vacía**.
- **R4** — Los anchos pasan a `DÍAS 14%` · `RANGO / NOMBRE 40%` · `WHATSAPP / CEL 18%` ·
  `LUGAR SERV. 28%`, sin reducir el tamaño de letra del documento (`7.5pt` actual).
- **R5** — Sin migraciones, sin cambios en el contrato HTTP, sin cambios de permisos y sin
  cambios en el frontend.

## Criterios de aceptación

**AC1 — La columna aparece con el dato**
- **Dado** un calendario con una semana aprobada que tiene asignaciones,
- **cuando** el encargado pulsa **PDF** en esa semana,
- **entonces** el documento muestra la cabecera `WHATSAPP / CEL` y cada fila de asignación
  lleva el número del médico correspondiente.

**AC2 — El relleno no se imprime**
- **Dado** un médico con `whatsapp_phone = '0000000000'`,
- **cuando** se exporta la semana en la que está asignado,
- **entonces** su celda de WhatsApp sale vacía y no contiene `0000000000`.

**AC3 — El resto del documento no cambia**
- **Dado** el mismo calendario antes y después del cambio,
- **entonces** las columnas `DÍAS`, `RANGO / NOMBRE` y `LUGAR SERV.`, el agrupamiento por día
  con `rowspan`, las bandas alternadas por día y el bloque de firmas siguen igual.

**AC4 — El contrato se mantiene**
- **Dado** el endpoint `GET /api/reports/calendar/{calendar_id}/weeks/{week_id}/pdf`,
- **entonces** sigue respondiendo `application/pdf` con `Content-Disposition: inline` y sigue
  exigiendo el permiso `export_reports`.

**AC5 — Semana sin asignaciones**
- **Dado** una semana sin asignaciones,
- **entonces** el endpoint sigue devolviendo `404` con `No hay asignaciones para el período`
  (comportamiento actual, `report_service.py:742-743`).

## Contrato

**No cambia el contrato HTTP.** Cambia la forma del payload interno `schedule_data` que
`build_weekly_schedule` le pasa a la plantilla: cada asignación gana la clave
`whatsapp_phone` (cadena, posiblemente vacía).

```python
# report_service.py — forma actual
{"rank_name": "CAP. PÉREZ, LUIS", "location": "EMERGENCIA"}

# después del cambio
{"rank_name": "CAP. PÉREZ, LUIS", "whatsapp_phone": "809-555-1234", "location": "EMERGENCIA"}
```

Consumidores de `schedule_data` en la plantilla usan `.get(...)`, así que la clave es
aditiva y no rompe a nadie.

## Impacto en tests

| Archivo | Efecto | Acción |
|---|---|---|
| `backend/tests/reports/test_report_service.py:565` | `test_build_weekly_schedule_pdf` **renderiza la plantilla real** (WeasyPrint) y su mock es `MagicMock()` sin `whatsapp_phone` | Añadir `mock_doc.whatsapp_phone`; opcionalmente asertar el número |
| `backend/tests/reports/test_week_report_service.py:6` | Igual: renderiza la plantilla real con mocks `MagicMock(id="doc1", name="LOPEZ, JUAN")` | Ídem |
| `backend/tests/reports/test_week_report_service.py:66` | Mockea `generate_weekly_schedule_pdf`, asertá `date_label` | Sin cambios; la clave nueva es aditiva |
| `backend/tests/reports/test_pdf_templates.py` | Prueba la versión **ReportLab**, que no es la que usa la app | Sin cambios |
| `backend/tests/reports/test_week_report_service.py` | **Nuevo**: `test_weekly_schedule_payload_includes_whatsapp_phone` (AC1), `test_weekly_schedule_blanks_unusable_phone` (AC2, parametrizado), `test_clean_phone_rejects_placeholder_and_non_strings` y `test_weekly_template_renders_whatsapp_column` | **Creados** |

> Corrección respecto a la investigación inicial: sí hay tests que renderizan
> `weekly_schedule.html` de verdad (`test_report_service.py:565` y
> `test_week_report_service.py:6` llaman a `build_weekly_schedule` sin mockear el generador).
> Por eso los mocks de médicos **deben** llevar el atributo; si no, un `MagicMock` termina
> impreso dentro del PDF.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| **Nombres largos apretados**: pasan de 52% a 40% | Revisar el PDF real con nombres largos antes de cerrar; si molesta, quitarle a `WHATSAPP / CEL` (18% → 15%) |
| **Un `MagicMock` impreso en el PDF** si un test no setea el atributo | El helper de limpieza devuelve `""` para cualquier valor que no sea `str`, así un mock nunca se imprime |
| **Filas con `0000000000`** en producción | Decidido: se imprimen vacías (R3). Vale la pena medir cuántas filas son, para saber si el encargado ve muchos huecos |
| **Privacidad**: el documento ahora lleva datos de contacto | Decisión 3: el PDF solo se descarga desde el panel |

## Hallazgo fuera de alcance — la lista semanal por Telegram está rota

`backend/app/application/telegram/tool_handlers.py:1116` usa `build_weekly_schedule(...)`,
que **devuelve bytes de PDF** (`report_service.py:747`), y luego pasa ese resultado como
`schedule_data=` a `generate_weekly_schedule_pdf(...)` en la línea `1122` — que espera una
lista de días. La plantilla itera sobre bytes y falla al hacer `day.get(...)`.

Es un defecto **preexistente** y ajeno a este cambio (el camino se rompe antes de llegar a la
plantilla), pero se documenta aquí porque se descubrió durante esta investigación. Queda
**fuera de alcance**: si se quiere arreglar, va en su propio spec.

## Lo que NO cambia

- Modelos de base de datos y migraciones (el campo existe desde `20260524_0040`)
- El formulario de médicos y la API de médicos (el campo ya está expuesto y es editable)
- El PDF del calendario completo y la grilla en pantalla
- Los permisos y el contrato del endpoint de exportación
- El PDF mensual y el resto de reportes (cobertura, carga, ficha)

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Nuevo requerimiento | Spec creada a partir del pedido del encargado de ver el WhatsApp/celular en la lista semanal en PDF. Se documenta que el campo ya existe en base de datos y API, por lo que el cambio se limita a la capa de reportes. Se registra como hallazgo fuera de alcance un defecto preexistente en el camino de Telegram. |
| 1.1.0 | 2026-10-09 | — | Implementación | Estado pasa a `implementado` en la rama `feat/whatsapp-pdf-semanal`. Columna `WHATSAPP / CEL` con anchos `14/40/18/28`, relleno `0000000000` impreso en blanco y helper `_clean_phone`. Durante los tests se corrigió un defecto de los mocks: `MagicMock(name=...)` no crea el atributo `.name`, así que el nombre del médico nunca llegaba al payload y un `repr` de mock se imprimía en el PDF. |
