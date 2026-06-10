# Doctors By Area — Spec

**Date:** 2026-06-10
**Status:** Draft
**Context:** El usuario quiere una pestaña "Por Área" en la sección de Médicos, que agrupe médicos por área de servicio (Emergencia, Pista, Disponible). Replica el patrón existente de la pestaña "Por Día" (`DoctorsByDay.tsx`).

---

## 1. Feature Overview

Nueva pestaña **"Por Área"** en `DoctorsPage` que muestra acordeones expandibles por área de servicio. Cada acordeón lista los médicos que tienen esa área asignada (vía `doctor_allowed_areas`).

- **3 columnas:** Nombre, Rango, Departamento
- **Permisos:** Solo encargado y admin (mismo guard que "Por Día")
- **Áreas vacías:** Placeholder "Sin médicos asignados"
- **Badge por área:** Iniciales con color distintivo (ej. EM para Emergencia en rojo, PI para Pista en naranja, DI para Disponible en verde)

---

## 2. Backend

### 2.1 Schemas — `backend/app/schemas/doctors.py`

Agregar al final del archivo:

```python
class DoctorByAreaItem(BaseModel):
    id: str
    name: str
    rank_name: str | None = None
    department_name: str | None = None

    model_config = {"from_attributes": True}


class AreaGroup(BaseModel):
    area_id: str
    code: str
    label: str
    count: int
    doctors: list[DoctorByAreaItem]


class DoctorByAreaResponse(BaseModel):
    areas: dict[str, AreaGroup]  # key = area_id
```

### 2.2 Service — `backend/app/application/doctors/service.py`

Agregar método `list_by_area()` en `DoctorService`:

```python
def list_by_area(self) -> dict:
    active_doctors = self.doctors.list_all(active_only=True)
    doctor_ids = [d.id for d in active_doctors]

    # Bulk-load allowed areas (doctor_id -> [area_id, ...])
    areas_by_doctor = self.doctors.get_allowed_areas_bulk(doctor_ids)

    # Load all active service areas
    all_areas = self.catalog_repo.list_service_areas()
    active_areas = [a for a in all_areas if a.active]

    # Load rank/department names
    ranks = {r.id: r.name for r in self.catalog_repo.list_ranks()} if self.catalog_repo else {}
    depts = {d.id: d.name for d in self.catalog_repo.list_departments()} if self.catalog_repo else {}

    # Initialize result: one entry per active area
    areas: dict[str, dict] = {
        a.id: {
            "area_id": a.id,
            "code": a.code,
            "label": a.display_name,
            "count": 0,
            "doctors": [],
        }
        for a in active_areas
    }

    for doctor in active_doctors:
        doc_area_ids = areas_by_doctor.get(doctor.id, [])
        for area_id in doc_area_ids:
            if area_id not in areas:
                continue  # skip areas that are inactive or unknown
            areas[area_id]["doctors"].append({
                "id": doctor.id,
                "name": doctor.name,
                "rank_name": ranks.get(doctor.rank_id),
                "department_name": depts.get(doctor.department_id),
            })
            areas[area_id]["count"] = len(areas[area_id]["doctors"])

    return {"areas": areas}
```

### 2.3 Route — `backend/app/api/routes/doctors.py`

Agregar después del endpoint `by-day`:

```python
@router.get("/by-area", response_model=DoctorByAreaResponse)
def list_doctors_by_area(
    _user: Annotated[UserModel, Depends(require_encargado_or_admin)],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
) -> dict:
    return service.list_by_area()
```

Importar `DoctorByAreaResponse` de `backend.app.schemas.doctors`.

---

## 3. Frontend

### 3.1 API Types — `frontend/src/api/doctors.ts`

Agregar interfaces:

```typescript
export interface DoctorByAreaItem {
  id: string;
  name: string;
  rank_name: string | null;
  department_name: string | null;
}

export interface AreaGroup {
  area_id: string;
  code: string;
  label: string;
  count: number;
  doctors: DoctorByAreaItem[];
}

export interface DoctorByAreaResponse {
  areas: Record<string, AreaGroup>;
}
```

Agregar método en `doctorsApi`:

```typescript
listByArea: () =>
  apiFetch<DoctorByAreaResponse>("/doctors/by-area"),
```

### 3.2 Component — `frontend/src/features/doctors/DoctorsByArea.tsx` (NUEVO)

Replica la estructura de `DoctorsByDay.tsx` con estas diferencias:

- **Query key:** `["doctors", "by-area"]`
- **Query fn:** `doctorsApi.listByArea`
- **Iteración:** `Object.entries(data.areas)` en vez de `DAY_KEYS`
- **Badge:** Usa `area.code.slice(0, 2).toUpperCase()` como texto del badge
- **Colores por área:** Mapa fijo basado en `area.code` (ej. EMERG → rojo, PISTA → naranja, DISPONIBLE → verde). Si un código no está en el mapa, usar un color default (gris).
- **Tabla:** Columnas **Nombre**, **Rango**, **Departamento** (sin WhatsApp, sin recurring_tag)
- **Vacías:** Mismo placeholder "Sin médicos asignados" con borde dashed
- **Leyenda:** No necesita leyenda (no hay recurring_tag)

Colores por código de área:

```typescript
const AREA_BADGE_COLORS: Record<string, { bg: string; text: string }> = {
  "EMERG": { bg: "#ef4444", text: "#fff" },
  "PISTA": { bg: "#f59e0b", text: "#fff" },
  "DISPONIBLE": { bg: "#10b981", text: "#fff" },
};
const DEFAULT_BADGE_COLOR = { bg: "#6b7280", text: "#fff" };
```

### 3.3 Page — `frontend/src/features/doctors/DoctorsPage.tsx`

Cambios mínimos:

1. **Importar** `DoctorsByArea` desde `"./DoctorsByArea"`
2. **Tipo Tab:** Cambiar de `"list" | "by-day"` a `"list" | "by-day" | "by-area"`
3. **Botón pestaña:** Agregar después del botón "Por Día", mismo patrón, mismo guard `isEncargadoPlus`
4. **Render:** Agregar condición `tab === "by-area" ? <DoctorsByArea /> : ...` (cambiar el ternario actual por una cadena de ifs o un switch)

---

## 4. Routing

No cambia. Todo es estado local en `DoctorsPage` (tab state).

---

## 5. Edge Cases

| Escenario | Comportamiento |
|-----------|---------------|
| Área sin médicos | Se muestra con borde dashed, "Sin médicos asignados" |
| Área inactiva en DB | No se incluye en la respuesta del backend (`active_areas` filtrado) |
| Médico sin áreas asignadas | No aparece en ninguna área |
| Médico en múltiples áreas | Aparece en cada área que tenga asignada |
| Usuario no encargado/admin | La pestaña no se renderiza (mismo guard `isEncargadoPlus`) |
| Error de red / API | `useQuery` maneja el error; el componente no renderiza (`if (!data) return null`) |

---

## 6. Files Modified / Created

| Archivo | Acción |
|---------|--------|
| `backend/app/schemas/doctors.py` | Agregar `DoctorByAreaItem`, `AreaGroup`, `DoctorByAreaResponse` |
| `backend/app/application/doctors/service.py` | Agregar método `list_by_area()` |
| `backend/app/api/routes/doctors.py` | Agregar endpoint `GET /by-area` + import |
| `frontend/src/api/doctors.ts` | Agregar tipos + `doctorsApi.listByArea()` |
| `frontend/src/features/doctors/DoctorsByArea.tsx` | **Nuevo** componente |
| `frontend/src/features/doctors/DoctorsPage.tsx` | Agregar tab "by-area" |

---

## 7. Verification

### Backend

```bash
cd backend
# Run existing tests to ensure no regressions
python -m pytest tests/ -x -q --tb=short
```

### Frontend

```bash
cd frontend
# Type check
npx tsc --noEmit
# Run existing tests
npx vitest run
```

### Manual E2E
1. Iniciar backend y frontend
2. Loguear como admin o encargado
3. Ir a Médicos → verificar que aparece la pestaña "Por Área"
4. Clic en "Por Área" → ver acordeones por área
5. Expandir un área → ver tabla con Nombre, Rango, Departamento
6. Verificar que áreas sin médicos muestran "Sin médicos asignados"
7. Loguear como usuario normal → verificar que NO ve la pestaña "Por Área"
