---
spec: search-highlight
version: 1.0.0
status: accepted
created: 2026-07-08
---

# Search & Highlight — Filtro disponibilidad mensual + Buscador en grilla

## Requerimiento 1 — Filtro availability_mode en listado de médicos

Agregar un checkbox en la pantalla de listado de médicos que al marcarlo filtre mostrando solo los médicos con `availability_mode = "monthly"` (los que dan su disponibilidad cada mes).

**Backend:**
- Endpoint `GET /api/doctors` acepta query param opcional `?availability_mode=monthly`
- `DoctorService.list_doctors()` recibe filtro opcional y lo pasa al repo
- `DoctorRepository.list_all()` acepta filtro por `availability_mode`

**Frontend:**
- Componente `DoctorList.tsx`: checkbox "Solo disponibilidad mensual" junto a otros controles
- Al marcar/desmarcar se re-fetcha la lista con el parámetro

## Requerimiento 2 — Buscador/resaltador en grilla del calendario

Agregar un input de búsqueda sobre la grilla del calendario que resalte visualmente las celdas donde aparezca el médico buscado.

**Solo frontend — sin llamadas al backend:**
- Input con placeholder "Buscar médico..."
- Al escribir 2+ caracteres, se buscan coincidencias (case-insensitive) en nombres y apellidos de médicos asignados en la grilla
- Las celdas coincidentes se resaltan con CSS (borde azul + background)
- Al limpiar el input, se quitan los resaltados
- Funciona sobre la data ya cargada del grid (no hay fetch adicional)

## Archivos afectados

| Archivo | Cambio | Riesgo |
|---|---|---|
| `backend/app/api/routes/doctors.py` | + query param opcional | Bajo — solo agregar parámetro |
| `backend/app/application/doctors/service.py` | + filtro en list_doctors | Bajo — parámetro opcional |
| `backend/app/infrastructure/repositories/doctors.py` | + WHERE condicional | Bajo — solo lectura |
| `frontend/src/api/doctors.ts` | + param opcional en fetch | Bajo — mismo patrón existente |
| `frontend/src/features/doctors/DoctorList.tsx` | + checkbox + lógica filtro | Medio — UI existente |
| `frontend/src/features/calendars/CalendarGrid.tsx` | + input búsqueda + resaltado | Medio — solo frontend |
| `frontend/src/features/calendars/CalendarGrid.css` | + clase .highlight | Bajo — CSS nuevo |

## Lo que NO cambia
- Modelos DB, migraciones
- Calendar engine, scoring, rules
- API de calendarios, reportes, Telegram
- Autenticación, auditoría
- Ciclo de generación de calendarios
