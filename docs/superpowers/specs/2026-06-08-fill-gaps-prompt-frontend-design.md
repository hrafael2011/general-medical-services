# Design: Fill-Gaps Prompt on Doctor Availability Change (Frontend)

## Context

When a doctor's `availability_mode` is changed or `service_active` is disabled, the backend now cleans up their assignments in draft/partial calendars (PR #6). The frontend needs to detect this and offer the user a choice: auto-fill the resulting gaps via `POST /fill-gaps` or fill them manually.

## Design

### Backend tweak

`PATCH /doctors/{id}` response gains two optional fields:
- `removed_assignments: int` — how many assignments were cleaned up
- `affected_calendar_ids: list[str]` — which calendars were affected

These fields are only present when assignments were actually removed.

### Frontend flow

1. User edits doctor (changes `availability_mode` or disables `service_active`)
2. User clicks "Guardar"
3. `PATCH /doctors/{id}` returns response
4. If `removed_assignments > 0` → show prompt modal BEFORE closing the doctor form
5. User chooses:
   - **Automático** → `POST /calendars/{id}/fill-gaps` for each affected calendar
   - **Manual** → close, user fills gaps from the calendar grid
6. Doctor form closes

### Files

| File | Change |
|---|---|
| `backend/app/api/routes/doctors.py` | Include `removed_assignments` + `affected_calendar_ids` in response |
| `frontend/src/api/doctors.ts` | Add optional fields to response type |
| `frontend/src/features/doctors/DoctorForm.tsx` | Add gap-fill prompt modal after successful save |

### UI

A simple confirm dialog inside the existing modal pattern: "Se eliminaron X asignaciones del Dr. [Nombre] en Y calendarios. ¿Desea rellenar los huecos automáticamente o prefiere hacerlo manualmente?" with two buttons: "Automático" and "Manual".
