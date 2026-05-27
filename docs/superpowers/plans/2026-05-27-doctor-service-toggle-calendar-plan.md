# Doctor Service Toggle + Calendar Picker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "¿Hace servicio?" toggle to doctor form and replace the monthly day grid with a real calendar using react-day-picker.

**Architecture:** Backend changes are minimal — `service_active` already exists on the model, just needs to be exposed in the create/update schemas and handled in the service layer. Frontend adds a toggle state that controls visibility of the availability section, and replaces the 1-31 number grid with `react-day-picker` DayPicker in `mode="multiple"`.

**Tech Stack:** FastAPI (Python), React + TypeScript, react-day-picker v9, SQLAlchemy

---

### Task 1: Backend — Expose `service_active` in schemas and service layer

**Files:**
- Modify: `backend/app/schemas/doctors.py:29-70`
- Modify: `backend/app/application/doctors/service.py:58-134` (create) and `service.py:136-278` (update)
- Modify: `backend/app/infrastructure/repositories/availability.py:12-62`

- [ ] **Step 1: Add `service_active` to `CreateDoctorRequest`**

In `backend/app/schemas/doctors.py`, add the field to `CreateDoctorRequest` (line ~38, after `participa_misiones`):

```python
class CreateDoctorRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=160)
    last_name: str | None = Field(default=None, min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    sex: str = Field(pattern="^(male|female)$")
    rank_id: str | None = None
    department_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
    participa_misiones: bool = True
    service_active: bool = True  # <-- ADD THIS
    whatsapp_phone: str | None = Field(default=None, max_length=40)
    # ... rest unchanged
```

- [ ] **Step 2: Add `service_active` to `UpdateDoctorRequest`**

In the same file, add to `UpdateDoctorRequest` (line ~64, after `participa_misiones`):

```python
class UpdateDoctorRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=160)
    last_name: str | None = Field(default=None, min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    sex: str | None = Field(default=None, pattern="^(male|female)$")
    rank_id: str | None = None
    department_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
    participa_misiones: bool | None = None
    service_active: bool | None = None  # <-- ADD THIS
    whatsapp_phone: str | None = Field(default=None, max_length=40)
    # ... rest unchanged
```

- [ ] **Step 3: Pass `service_active` through `create_doctor`**

In `backend/app/application/doctors/service.py`, add the parameter to `create_doctor` (line ~70, after `participa_misiones`):

```python
def create_doctor(
    self,
    *,
    actor_id: str,
    sex: str,
    name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    rank_id: str | None = None,
    department_id: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
    participa_misiones: bool = True,
    service_active: bool = True,  # <-- ADD THIS
    whatsapp_phone: str | None = None,
    # ... rest unchanged
```

And use it in the `DoctorModel` constructor (line ~116, replace `service_active=True`):

```python
service_active=service_active,  # <-- was hardcoded True
```

- [ ] **Step 4: Add `delete_all_for_doctor` to `AvailabilityRepository`**

In `backend/app/infrastructure/repositories/availability.py`, add after `delete_availability` (after line ~61):

```python
def delete_all_for_doctor(self, doctor_id: str) -> None:
    stmt = select(DoctorAvailabilityModel).where(
        DoctorAvailabilityModel.doctor_id == doctor_id
    )
    records = list(self.session.scalars(stmt))
    for record in records:
        self.session.delete(record)
    if records:
        self.session.flush()
```

- [ ] **Step 5: Handle `service_active` changes in `update_doctor`**

In `backend/app/application/doctors/service.py`, in the `update_doctor` method, add `service_active` parameter (after `participa_misiones` around line ~149):

```python
def update_doctor(
    self,
    doctor_id: str,
    *,
    actor_id: str,
    # ... existing params ...
    participa_misiones: bool | None = None,
    service_active: bool | None = None,  # <-- ADD THIS
    whatsapp_phone: str | None | object = _MISSING,
    # ... rest unchanged
```

Add the handling logic before `doctor.updated_at = datetime.now(UTC)` (~line 269):

```python
if service_active is not None:
    doctor.service_active = service_active
    changed_fields["service_active"] = service_active
    if not service_active:
        from backend.app.infrastructure.repositories.availability import AvailabilityRepository
        AvailabilityRepository(self.doctors.session).delete_all_for_doctor(doctor_id)
        if allowed_area_ids is None:
            self.doctors.set_allowed_areas(doctor_id, [])
            changed_fields["allowed_area_ids"] = []
```

- [ ] **Step 6: Pass `service_active` in the API route**

In `backend/app/api/routes/doctors.py`, add `service_active=payload.service_active` in both `create_doctor` (~line 93) and ensure `update_doctor` passes it via `**update_fields`.

No changes needed — `create_doctor` already passes individual fields (add the line), and `update_doctor` uses `**update_fields` which will include it automatically once added to the schema.

Add in `create_doctor`:
```python
service_active=payload.service_active,
```

- [ ] **Step 7: Commit backend changes**

```bash
git add backend/app/schemas/doctors.py backend/app/application/doctors/service.py backend/app/infrastructure/repositories/availability.py backend/app/api/routes/doctors.py
git commit -m "feat: expose service_active in doctor create/update schemas and service layer"
```

---

### Task 2: Frontend — Add "¿Hace servicio?" toggle

**Files:**
- Modify: `frontend/src/features/doctors/DoctorForm.tsx:1-371`
- Modify: `frontend/src/api/doctors.ts:20-31`

- [ ] **Step 1: Add `service_active` to `CreateDoctorPayload`**

In `frontend/src/api/doctors.ts`, add the field:

```typescript
export interface CreateDoctorPayload {
  first_name?: string | null; last_name?: string | null;
  name?: string; sex: string;
  rank_id?: string | null; department_id?: string | null;
  phone?: string | null; notes?: string | null;
  participa_misiones: boolean;
  service_active?: boolean;  // <-- ADD THIS
  whatsapp_phone?: string | null;
  monthly_service_target: number; monthly_service_max: number;
  monthly_service_limit_mode: string; availability_mode: string;
  allowed_area_ids: string[];
}
```

- [ ] **Step 2: Add `doesService` state and toggle to `DoctorForm`**

In `frontend/src/features/doctors/DoctorForm.tsx`:

Add state (after `participaMisiones`, line ~20):
```typescript
const [doesService, setDoesService] = useState(doctor?.service_active ?? true);
```

Add toggle UI before the availability `<fieldset>` (before line ~243):

```tsx
<label className="check-label">
  <input
    type="checkbox"
    checked={doesService}
    onChange={e => {
      setDoesService(e.target.checked);
      if (!e.target.checked) {
        setAllowedAreaIds([]);
      }
    }}
  />
  ¿Hace servicio?
</label>
```

- [ ] **Step 3: Conditionally hide availability section**

Wrap the availability `<fieldset>` (lines 242-321) in a conditional:

```tsx
{doesService && (
  <div className="form-row">
    <fieldset className="field-group">
      <legend>Disponibilidad</legend>
      {/* ... existing av-toggle-group and mode content unchanged ... */}
    </fieldset>
  </div>
)}
```

- [ ] **Step 4: Hide areas fieldset when service is off, and show info text**

Wrap the areas `<fieldset>` (lines 323-337) and also show a message when `doesService` is false:

```tsx
{doesService ? (
  <>
    <fieldset className="field-group">
      <legend>Áreas de servicio permitidas</legend>
      {/* ... existing area checks ... */}
    </fieldset>
  </>
) : (
  <p style={{ color: "#64748b", fontSize: "0.85rem", margin: "8px 0" }}>
    El médico no estará disponible para turnos de servicio.
  </p>
)}
```

- [ ] **Step 5: Update `handleSubmit` to send `service_active` and skip validation when service is off**

In `handleSubmit` (line 129), modify the validation to skip availability checks when `doesService` is false:

```typescript
function handleSubmit(e: FormEvent) {
  e.preventDefault();
  setError("");
  const t = parseInt(target, 10);
  const m = parseInt(max, 10);
  if (isNaN(t) || isNaN(m)) { setError("Meta y máximo deben ser números."); return; }

  if (doesService) {
    if (avMode === "weekly" && selectedDays.length === 0) { setError("Selecciona al menos un día de la semana."); return; }
    if (avMode === "monthly" && selectedDates.length === 0) { setError("Selecciona al menos un día del mes."); return; }
  }

  const availabilityMode = avMode === "monthly" ? "monthly" : "fixed";

  const cleanFirstName = firstName.trim();
  const cleanLastName = lastName.trim();
  const fullName = [cleanFirstName, cleanLastName].filter(Boolean).join(" ");
  if (!cleanFirstName || !cleanLastName) { setError("Nombre y apellido son obligatorios."); return; }

  save.mutate({
    first_name: cleanFirstName,
    last_name: cleanLastName,
    name: fullName,
    sex, phone: phone || null, participa_misiones: participaMisiones,
    service_active: doesService,  // <-- ADD THIS
    rank_id: rankId || null,
    department_id: departmentId || null,
    availability_mode: availabilityMode,
    monthly_service_target: t, monthly_service_max: m,
    monthly_service_limit_mode: limitMode,
    allowed_area_ids: doesService ? allowedAreaIds : [],  // <-- MODIFIED
  });
}
```

- [ ] **Step 6: Update the save `onSuccess` to skip availability when service is off**

In the `save` mutation `onSuccess` (lines 101-118), wrap the availability calls:

```typescript
onSuccess: async (savedDoctor) => {
  const doctorId = savedDoctor.id;
  if (doesService) {
    try {
      if (avMode === "weekly" && selectedDays.length > 0) {
        await availabilityApi.setWeekly(doctorId, { days_of_week: selectedDays });
      } else if (avMode === "monthly" && selectedDates.length > 0) {
        const now = new Date();
        await availabilityApi.setMonthly(doctorId, {
          year: now.getFullYear(),
          month: now.getMonth() + 1,
          available_dates: selectedDates,
        });
      } else if (avMode === "recurring") {
        await availabilityApi.setRecurring(doctorId, {
          weekday: selectedWeekday,
          week_number: selectedWeekNumber,
        });
      }
    } catch {
      setError("Médico guardado, pero no se pudo configurar la disponibilidad.");
      return;
    }
  }
  qc.invalidateQueries({ queryKey: ["doctors"] });
  onClose();
},
```

- [ ] **Step 7: Commit toggle changes**

```bash
git add frontend/src/api/doctors.ts frontend/src/features/doctors/DoctorForm.tsx
git commit -m "feat: add ¿Hace servicio? toggle to doctor form"
```

---

### Task 3: Frontend — Replace monthly grid with react-day-picker DayPicker

**Files:**
- Create: (install dependency via npm)
- Modify: `frontend/src/features/doctors/DoctorForm.tsx:34-54` and `DoctorForm.tsx:282-292`

- [ ] **Step 1: Install react-day-picker**

```bash
cd frontend && npm install react-day-picker
```

- [ ] **Step 2: Import DayPicker in DoctorForm**

In `frontend/src/features/doctors/DoctorForm.tsx`, add import at the top:

```typescript
import { DayPicker } from "react-day-picker";
import "react-day-picker/style.css";
```

- [ ] **Step 3: Replace the `selectedDates` state type and toggle function**

Change `selectedDates` from `number[]` to `Date[]` (line 38):

```typescript
const [selectedDates, setSelectedDates] = useState<Date[]>([]);
```

Replace `toggleDate` (lines 50-54) with:

```typescript
function handleDayPickerSelect(dates: Date[] | undefined) {
  setSelectedDates(dates ?? []);
}
```

- [ ] **Step 4: Replace the monthly grid JSX with DayPicker**

Replace lines 282-292 (the `av-month-grid` div) with:

```tsx
{avMode === "monthly" && (
  <div className="av-calendar">
    <DayPicker
      mode="multiple"
      selected={selectedDates}
      onSelect={handleDayPickerSelect}
      fromMonth={new Date()}
      defaultMonth={new Date()}
      showOutsideDays={false}
    />
  </div>
)}
```

- [ ] **Step 5: Update the submit logic to convert Date[] to day numbers**

In `onSuccess` where monthly availability is saved (line ~107), convert dates:

```typescript
} else if (avMode === "monthly" && selectedDates.length > 0) {
  const dates = selectedDates;
  const year = dates[0].getFullYear();
  const month = dates[0].getMonth() + 1;
  const dayNumbers = dates.map(d => d.getDate());
  await availabilityApi.setMonthly(doctorId, {
    year,
    month,
    available_dates: dayNumbers,
  });
}
```

- [ ] **Step 6: Handle editing existing monthly data (convert number[] from API to Date[])**

In the `useEffect` that loads existing availability (line ~93), update the monthly case:

```typescript
} else if (monthly) {
  setAvMode("monthly");
  const year = monthly.year ?? new Date().getFullYear();
  const month = monthly.month ?? new Date().getMonth() + 1;
  setSelectedDates(
    (monthly.available_dates ?? []).map(d => new Date(year, month - 1, d))
  );
}
```

- [ ] **Step 7: Commit calendar changes**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/features/doctors/DoctorForm.tsx
git commit -m "feat: replace monthly day grid with react-day-picker calendar"
```

---

### Task 4: CSS — Styles for toggle info text and calendar

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add calendar container and DayPicker override styles**

In `frontend/src/styles.css`, add after the existing availability styles (~line 1440):

```css
/* Calendar (react-day-picker overrides) */
.av-calendar {
  margin-left: 22px;
  margin-top: 8px;
}

.av-calendar .rdp {
  --rdp-accent-color: #2563eb;
  --rdp-background-color: #eff6ff;
  --rdp-day-width: 36px;
  --rdp-day-height: 36px;
  font-size: 0.78rem;
}

.av-calendar .rdp-nav_button {
  border: 0;
  background: transparent;
  cursor: pointer;
  color: #475569;
}

.av-calendar .rdp-nav_button:hover {
  color: #2563eb;
}

.av-calendar .rdp-day_selected {
  background: #2563eb;
  color: #fff;
  border-radius: 50%;
}

.av-calendar .rdp-day_selected:hover {
  background: #1d4ed8;
}

.av-calendar .rdp-day:hover:not(.rdp-day_selected) {
  background: #eff6ff;
  border-radius: 50%;
}
```

- [ ] **Step 2: Commit CSS changes**

```bash
git add frontend/src/styles.css
git commit -m "style: add calendar and toggle styles to doctor form"
```

---

## Verification

1. **Create doctor with `service_active=False`**: Form shows toggle unchecked, no availability options, no areas. Submit saves doctor without availability records.
   - Run: `pytest backend/tests/doctors/ -v -k "create"` if tests exist
2. **Create doctor with `service_active=True` + monthly mode**: Toggle checked, DayPicker visible. Select days → submit. Verify `available_dates` are saved as int array.
3. **Edit doctor: toggle service from True to False**: Existing availability records are deleted. Areas are cleared.
4. **Edit doctor: toggle service from False to True**: Availability section appears, can configure from scratch.
5. **Calendar**: Cannot navigate to months before current. Can navigate forward. Multiple day selection works.
6. **Calendar**: Days outside current month are hidden (`showOutsideDays={false}`).
