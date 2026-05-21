# Doctor Availability Form — Design

**Date:** 2026-05-11
**Status:** Draft

## Problem

The doctor creation/edit form (`DoctorForm.tsx`) has an `availability_mode` dropdown with cryptic values "Variable mensual" and "Fijo semanal". There is no UI to actually configure which days a doctor works. The backend already has a full `DoctorAvailability` model and API endpoints (`POST /availability/doctors/{id}/weekly`, `POST /availability/doctors/{id}/monthly`), but the frontend never calls them.

## Solution

Replace the `availability_mode` dropdown with three radio-button options using plain-Spanish labels, each revealing the corresponding controls:

```
¿Cómo es su disponibilidad?

○ Trabaja los mismos días todas las semanas
   → Checkboxes: Dom Lun Mar Mié Jue Vie Sáb

○ Avisa sus días cada mes
   → Selector de días del mes (mini calendario o checkboxes 1-31)

○ Tiene un día fijo al mes
   → Día: [Lun|Mar|Mié|Jue|Vie|Sáb|Dom]
     Semana: [1ra|2da|3ra|4ta|Última]
```

### What stays the same

| Item | File | Why |
|------|------|-----|
| Doctor model fields (name, sex, rank, phone, meta, max, etc.) | `DoctorForm.tsx` | Unchanged |
| Areas de servicio permitidas | `DoctorForm.tsx` | Unchanged |
| Participa en misiones | `DoctorForm.tsx` | Unchanged |
| Create/Update API endpoints | `api/doctors.ts` | Doctor CRUD unchanged |
| Backend `DoctorAvailability` model | `backend/` | Already supports all three modes |
| Backend availability API routes | `backend/` | Already implemented |

### What changes

| File | Change |
|------|--------|
| `frontend/src/api/doctors.ts` | Add `availabilityApi` with `setWeekly()`, `setMonthly()`, `setRecurring()` methods |
| `frontend/src/features/doctors/DoctorForm.tsx` | Replace `availability_mode` dropdown with radio group + conditional controls. On save, call availability API in addition to doctor API. |
| `frontend/src/styles.css` | Add styles for radio group, day checkboxes, recurring-day selectors |

## Design Details

### Option 1: Fixed weekly days

```
○ Trabaja los mismos días todas las semanas

  [Dom] [Lun] [Mar] [Mié] [Jue] [Vie] [Sáb]
         ✓     ✓                 ✓
```

- Each day is a toggle button/chip. Selected = highlighted.
- At least one day required when this mode is selected.
- Stored as `availability_type = "weekly"`, `days_of_week = [0,1,2,3,4,5,6]` (0=Monday...6=Sunday).
- Backend mapping: displayed as Dom=6, Lun=0, Mar=1, Mié=2, Jue=3, Vie=4, Sáb=5.

### Option 2: Monthly availability

```
○ Avisa sus días cada mes

  Mes actual: Mayo 2026
  [1] [2] [3] [4] [5] [6] [7]
  [8] [9] [10] [11] [12] [13] [14]
  [15] [16] [17] [18] [19] [20] [21]
  [22] [23] [24] [25] [26] [27] [28]
  [29] [30] [31]
```

- Simple grid of day numbers 1-31. Click to toggle selected.
- Stores selected days as `available_dates: [5, 12, 20]`.
- Calendar navigation (prev/next month) if needed.
- **On create (new doctor):** Could show current month. The user sets the initial availability.
- **On edit:** Shows the month of the existing availability record, or current month if none.

### Option 3: Recurring day (e.g., last Friday)

```
○ Tiene un día fijo al mes

  Día:    [Lun] [Mar] [Mié] [Jue] [Vie] [Sáb] [Dom]
          (single selection)

  Semana: [1ra] [2da] [3ra] [4ta] [Última]
          (single selection)
```

- Day: single-selection toggle buttons.
- Week: single-selection toggle buttons.
- Stored as `availability_type = "recurring"`, `weekday = 4`, `week_number = -1` for "last Friday".
- Week numbers: 0=1ra, 1=2da, 2=3ra, 3=4ta, -1=Última.

### Interaction on Save

When the form saves:

```typescript
// 1. Save doctor (existing behavior)
await doctorsApi.create(payload);  // or update

// 2. Save availability based on selected mode
if (mode === "weekly") {
  await availabilityApi.setWeekly(doctorId, { days_of_week: selectedDays });
} else if (mode === "monthly") {
  await availabilityApi.setMonthly(doctorId, { year, month, available_dates: selectedDates });
} else if (mode === "recurring") {
  await availabilityApi.setRecurring(doctorId, { weekday, week_number });
}
```

Note: On create, the `doctorId` is not known until the doctor is created. The flow is:
1. Create doctor → get `doctorId` from response
2. Set availability using `doctorId`

For edit, both calls can happen in parallel (or sequentially).

### States

| State | Behavior |
|-------|----------|
| Loading (edit) | Pre-select existing availability from API |
| No availability set yet | All modes unselected, show prompt to configure |
| Validation error | Show inline error if required fields missing |
| Save error | Show error message, keep form open |

### Backend Mapping

The backend model `DoctorAvailabilityModel` stores:

| Field | Weekly | Monthly | Recurring |
|-------|--------|---------|-----------|
| `availability_type` | `"weekly_fixed"` | `"monthly_variable"` | `"recurring"` (new) |
| `days_of_week` | `[1,3]` | `null` | `null` |
| `available_dates` | `null` | `[5,12,20]` | `null` |
| `weekday` | `null` | `null` | `4` (Friday) |
| `week_number` | `null` | `null` | `-1` (last) |
| `year` | `null` | `2026` | `null` |
| `month` | `null` | `5` | `null` |

Doctor `availability_mode` values (separate from availability record):
- `"fixed"` — for weekly and recurring modes
- `"monthly"` — for monthly mode

The backend validates that `doctor.availability_mode` matches the availability type being set (weekly availability requires `availability_mode = "fixed"`, monthly requires `"monthly"`).

Note: Adding `"recurring"` as a new `availability_type`. If the backend `SetWeeklyAvailabilityRequest` / `SetMonthlyAvailabilityRequest` schemas don't support recurring, a new endpoint or schema may be needed.

### Edge Cases

| Case | Handling |
|------|----------|
| Doctor with no availability config | All radio options unselected, save skips availability API call |
| Switching from weekly to monthly | Clear previous selection, show monthly picker |
| Editing doctor with existing availability | Fetch availability data and pre-select mode + values |
| Month with <31 days | Day numbers beyond month length are grayed out |
| New doctor (no ID yet) | Two-step save: create doctor first, then set availability |

## Implementation Order

1. Add `availabilityApi` to `api/doctors.ts`
2. Add CSS classes for radio group, day chips, recurring selectors
3. Rewrite availability section of `DoctorForm.tsx`
4. Test: create doctor with weekly availability
5. Test: create doctor with monthly availability
6. Test: edit existing doctor availability
7. Verify backend handles recurring type

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Backend doesn't support "recurring" availability type | Verify `availability_type` accepts "recurring" or add support |
| Two-step save (create + availability) could partially fail | Add error handling: if availability save fails, show error but doctor is already created |
| Existing doctors with `availability_mode` set but no availability records | Handle gracefully — show form with defaults, no data loss |
