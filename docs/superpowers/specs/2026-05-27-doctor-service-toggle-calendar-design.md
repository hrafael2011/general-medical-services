# Doctor Service Toggle + Calendar — Design Spec

**Date:** 2026-05-27
**Status:** Approved

---

## Context

El formulario de registro de médico actualmente asume que todo médico hace servicio. No hay forma de indicar que un médico **no** participa en turnos. Además, la selección de días en modo "da su día" es una simple cuadrícula 1-31 sin contexto de calendario real (días de la semana, mes visible, navegación entre meses).

## Requirements

1. **Toggle "¿Hace servicio?"** en el formulario de médico (crear y editar)
   - SÍ (default): muestra modalidades de disponibilidad (semanal / da su día / día fijo)
   - NO: oculta todo lo de disponibilidad, guarda `service_active=False`, borra availability si ya existía
2. **Calendario real** para modo "da su día" (monthly): reemplaza la cuadrícula 1-31 con `react-day-picker`, navegación solo hacia adelante

## Design

### Frontend: Toggle "¿Hace servicio?"

**Archivo:** `frontend/src/features/doctors/DoctorForm.tsx`

- Nuevo estado local: `const [doesService, setDoesService] = useState<boolean>(doctor?.service_active ?? true)`
- Switch/toggle ubicado **arriba** de la sección de modalidades de disponibilidad (~línea 242)
- **Cuando `doesService === true`**: comportamiento actual (3 modalidades con sus controles)
- **Cuando `doesService === false`**: se ocultan modalidades, días, calendario. Se muestra texto: *"El médico no estará disponible para turnos de servicio."*
- En edición, si cambia de `true` a `false`: no se envía payload de availability, el backend limpia los registros existentes
- El payload incluye `service_active: doesService`

### Frontend: Calendario con react-day-picker

**Archivo:** `frontend/src/features/doctors/DoctorForm.tsx`

- Reemplaza la cuadrícula `av-month-grid` (líneas 282-291) por `<DayPicker>` de `react-day-picker`
- Modo: selección múltiple (`mode="multiple"`)
- Solo se usa cuando `avMode === "monthly"`
- **Navegación**: `fromMonth={new Date()}` — no permite ir a meses pasados. `toMonth` sin límite (solo hacia adelante)
- **Estilos**: import `react-day-picker/style.css` + overrides en `styles.css`
- Días seleccionados: enlazados con `selectedDates` (Date[]) en lugar de `number[]`

**Conversión de datos**: El backend espera `available_dates: list[int]` (números de día 1-31). El `DayPicker` produce `Date[]`. La conversión se hace en el frontend: `selectedDates.map(d => d.getDate())`. El backend no requiere cambios para esto.

### Frontend: Dependencia nueva

```json
// package.json
"react-day-picker": "^9.x"
```

### Backend: Limpiar availability al desactivar servicio

**Archivo:** `backend/app/api/routes/doctors.py` — endpoint `update_doctor` (PATCH)

- Si `payload.service_active == False` y el doctor antes tenía `service_active == True`: llamar a `availability_service.delete_all_for_doctor(doctor_id)`

**Archivo:** `backend/app/application/availability/service.py`

- Nuevo método `delete_all_for_doctor(doctor_id: str)` — borra todos los registros en `doctor_availability` para ese doctor

**Archivo:** `backend/app/application/doctors/service.py`

- En `update_doctor`, si `service_active` pasa a `False`: limpiar `allowed_area_ids` (quitar áreas asignadas)

### CSS

**Archivo:** `frontend/src/styles.css`

- Estilos para el toggle switch (`.service-toggle`)
- Estilos para el contenedor del calendario (`.av-calendar`)
- Overrides de `react-day-picker` para consistencia visual con el tema
- La clase `.av-month-grid` se elimina o se reemplaza

## Data Flow

```
[Toggle ¿Hace servicio?]
        │
        ├── SÍ → [Modalidades: Semanal | Da su día | Día fijo]
        │              │
        │              ├── Semanal → checkboxes días (sin cambios)
        │              ├── Da su día → <DayPicker> (nuevo)
        │              └── Día fijo → chips weekday/weeknumber (sin cambios)
        │
        └── NO → service_active=False, sin availability, sin áreas
```

## Edge Cases

1. **Médico existente cambia de SÍ a NO**: Se borra su `doctor_availability` y `doctor_allowed_areas`
2. **Médico existente cambia de NO a SÍ**: Aparecen las modalidades vacías, debe configurar desde cero
3. **Mes con <31 días**: El calendario real maneja esto nativamente — solo muestra los días que existen
4. **Navegación bloqueada hacia atrás**: `fromMonth={new Date()}`, la flecha izquierda no aparece o está disabled en el mes actual
5. **Formato de fechas**: Las fechas seleccionadas se envían como `YYYY-MM-DD` al backend

## Verification

1. Crear médico con `service_active=False` → se guarda sin availability ni áreas
2. Crear médico con `service_active=True` → modalidad "da su día" → seleccionar días en calendario → se guardan las fechas correctamente
3. Editar médico: cambiar de SÍ a NO → se borra su availability anterior
4. Editar médico: cambiar de NO a SÍ → aparecen opciones, puede configurar disponibilidad
5. Calendario: no permite navegar a meses anteriores al actual
6. Calendario: permite seleccionar múltiples días, navegar meses hacia adelante
7. Listado de médicos: filtrar por departamento/rango muestra médicos con y sin servicio
