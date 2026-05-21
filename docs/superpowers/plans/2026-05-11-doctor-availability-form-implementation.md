# Doctor Availability Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three availability mode options to the DoctorForm with corresponding backend support.

**Architecture:** The backend already has weekly and monthly availability endpoints; recurring (e.g., "last Friday") needs a new endpoint. The frontend replaces the confusing `availability_mode` dropdown with radio buttons and conditional controls, calling the availability API after saving the doctor.

**Tech Stack:** FastAPI (backend), React + TanStack Query (frontend), CSS (styles)

---

### Task 1: Add recurring availability endpoint (backend)

**Files:**
- Modify: `backend/app/application/availability/service.py` — add method
- Modify: `backend/app/api/routes/availability.py` — add route + schema

- [ ] **Step 1: Read the existing service to understand patterns**

Read `backend/app/application/availability/service.py` (full file), then `backend/app/schemas/availability.py`, then `backend/app/api/routes/availability.py`.

- [ ] **Step 2: Add `SetRecurringAvailabilityRequest` schema**

In `backend/app/schemas/availability.py`, add:

```python
class SetRecurringAvailabilityRequest(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0=Monday to 6=Sunday")
    week_number: int = Field(description="0=first, 1=second, 2=third, 3=fourth, -1=last")
```

- [ ] **Step 3: Add `set_recurring_availability` service method**

In `backend/app/application/availability/service.py`, add after `set_monthly_availability`:

```python
def set_recurring_availability(
    self,
    doctor_id: str,
    *,
    weekday: int,
    week_number: int,
    actor_id: str,
) -> DoctorAvailabilityModel:
    doctor = self.doctors.get_by_id(doctor_id)
    if doctor is None:
        raise AvailabilityError("doctor_not_found", f"Doctor {doctor_id} not found")
    if doctor.availability_mode != "fixed":
        raise AvailabilityError(
            "mode_mismatch",
            "Recurring availability requires doctor availability_mode = 'fixed'.",
        )
    if not 0 <= weekday <= 6:
        raise AvailabilityError("invalid_weekday", "weekday must be 0 (Monday) to 6 (Sunday).")
    if week_number not in (-1, 0, 1, 2, 3):
        raise AvailabilityError("invalid_week_number", "week_number must be -1 (last) or 0-3.")

    now = datetime.now(UTC)
    record = DoctorAvailabilityModel(
        id=str(uuid.uuid4()),
        doctor_id=doctor_id,
        availability_type="recurring",
        days_of_week=None,
        available_dates=None,
        weekday=weekday,
        week_number=week_number,
        year=None,
        month=None,
        submitted_at=None,
        effective_from=None,
        effective_to=None,
        source="manual",
        review_status="approved",
        created_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    result = self.availability.add_availability(record)
    if self.audit:
        self.audit.log_availability_set(actor_id=actor_id, availability=result)
    return result
```

- [ ] **Step 4: Add route in availability router**

In `backend/app/api/routes/availability.py`, after the monthly endpoint:

```python
@router.post("/doctors/{doctor_id}/recurring", response_model=AvailabilityRead, status_code=201)
def set_recurring_availability(
    doctor_id: str,
    body: SetRecurringAvailabilityRequest,
    service: Annotated[AvailabilityService, Depends(get_availability_service)],
    current_user: Annotated[UserRead, Depends(get_current_user)],
):
    try:
        result = service.set_recurring_availability(
            doctor_id=doctor_id,
            weekday=body.weekday,
            week_number=body.week_number,
            actor_id=current_user.id,
        )
        return result
    except AvailabilityError as exc:
        raise _availability_error_to_http(exc)
```

Also add the import for `SetRecurringAvailabilityRequest` at the top.

- [ ] **Step 5: Verify backend compiles**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/backend && python3 -c "from app.main import app; print('OK')"`

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/availability.py backend/app/application/availability/service.py backend/app/api/routes/availability.py
git commit -m "feat(api): add recurring availability endpoint"
```

---

### Task 2: Add availabilityApi to frontend API client

**Files:**
- Modify: `frontend/src/api/doctors.ts`

- [ ] **Step 1: Read the current file to know where to add**

- [ ] **Step 2: Add API methods**

Add at the end of `frontend/src/api/doctors.ts` (before the closing export):

```typescript
export const availabilityApi = {
  setWeekly: (doctorId: string, body: { days_of_week: number[]; effective_from?: string; effective_to?: string }) =>
    apiFetch<unknown>(`/availability/doctors/${doctorId}/weekly`, { method: "POST", body: JSON.stringify(body) }),
  setMonthly: (doctorId: string, body: { year: number; month: number; available_dates: number[] }) =>
    apiFetch<unknown>(`/availability/doctors/${doctorId}/monthly`, { method: "POST", body: JSON.stringify(body) }),
  setRecurring: (doctorId: string, body: { weekday: number; week_number: number }) =>
    apiFetch<unknown>(`/availability/doctors/${doctorId}/recurring`, { method: "POST", body: JSON.stringify(body) }),
  list: (doctorId: string) =>
    apiFetch<unknown[]>(`/availability/doctors/${doctorId}`),
};
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/doctors.ts
git commit -m "feat(api): add availabilityApi client methods"
```

---

### Task 3: Add CSS classes for new form controls

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Read the current styles.css to find a good insertion point**

Read around the doctor-form section.

- [ ] **Step 2: Add styles for radio group, day chips, recurring selectors**

```css
/* ===== Doctor availability form ===== */
.av-mode-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.av-mode-option {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.av-mode-radio {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
}

.av-mode-radio input[type="radio"] {
  accent-color: #2563eb;
}

.av-day-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-left: 22px;
}

.av-day-chip {
  width: 36px;
  height: 30px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 600;
  color: #475569;
  transition: all 0.1s;
}

.av-day-chip:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.av-day-chip--selected {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.av-day-chip--selected:hover {
  background: #1d4ed8;
}

.av-month-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  margin-left: 22px;
  max-width: 280px;
}

.av-month-day {
  width: 100%;
  aspect-ratio: 1;
  border: 1px solid #e2e8f0;
  border-radius: 3px;
  background: #fff;
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 600;
  color: #475569;
  transition: all 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.av-month-day:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.av-month-day--selected {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.av-month-day--filler {
  border-color: transparent;
  cursor: default;
  background: transparent;
}

.av-month-day--outside {
  color: #cbd5e1;
}

.av-recurring-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-left: 22px;
}

.av-recurring-col {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.av-recurring-label {
  font-size: 0.7rem;
  color: #64748b;
  font-weight: 600;
  margin-bottom: 2px;
}

.av-recurring-chip {
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 600;
  color: #475569;
  transition: all 0.1s;
}

.av-recurring-chip:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.av-recurring-chip--selected {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.av-recurring-chip--selected:hover {
  background: #1d4ed8;
}
```

- [ ] **Step 3: Add to styles.css**

Find the right place in styles.css (after existing doctor-form or field-group styles) and append the CSS block.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style(doctor): add availability form CSS classes"
```

---

### Task 4: Rewrite availability section in DoctorForm.tsx

**Files:**
- Modify: `frontend/src/features/doctors/DoctorForm.tsx`

- [ ] **Step 1: Read current DoctorForm.tsx**

- [ ] **Step 2: Replace the availability section**

Replace the current dropdown at lines 126-134:

```tsx
{/* Current dropdown to remove */}
<div className="form-row">
  <label>
    Modo disponibilidad
    <select value={availabilityMode} onChange={e => setAvailabilityMode(e.target.value)}>
      <option value="monthly">Variable mensual</option>
      <option value="fixed">Fijo semanal</option>
    </select>
  </label>
</div>
```

With the new radio group + conditional controls. Add state variables:

```tsx
const AVAIL_MODES = ["weekly", "monthly", "recurring"] as const;
type AvMode = (typeof AVAIL_MODES)[number];

const DAY_LABELS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
// Maps display index (0=Dom) to backend value (0=Monday)
const DAY_TO_BACKEND = [6, 0, 1, 2, 3, 4, 5];
const BACKEND_TO_DAY = [1, 2, 3, 4, 5, 6, 0];

const WEEK_LABELS = ["1ra", "2da", "3ra", "4ta", "Última"];
const WEEK_VALUES = [0, 1, 2, 3, -1];

const [avMode, setAvMode] = useState<AvMode>("weekly");
const [selectedDays, setSelectedDays] = useState<number[]>([]);
const [selectedDates, setSelectedDates] = useState<number[]>([]);
const [selectedWeekday, setSelectedWeekday] = useState<number>(4); // Friday default
const [selectedWeekNumber, setSelectedWeekNumber] = useState<number>(-1); // Last default

function toggleDay(backendDay: number) {
  setSelectedDays(prev =>
    prev.includes(backendDay) ? prev.filter(d => d !== backendDay) : [...prev, backendDay]
  );
}

function toggleDate(day: number) {
  setSelectedDates(prev =>
    prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
  );
}
```

Then the JSX:

```tsx
<div className="form-row">
  <fieldset className="field-group">
    <legend>Disponibilidad</legend>
    <div className="av-mode-group">
      {/* Option 1: Fixed weekly */}
      <div className="av-mode-option">
        <label className="av-mode-radio">
          <input type="radio" name="avMode" checked={avMode === "weekly"} onChange={() => setAvMode("weekly")} />
          Trabaja los mismos días todas las semanas
        </label>
        {avMode === "weekly" && (
          <div className="av-day-chips">
            {DAY_LABELS.map((label, i) => {
              const backendDay = DAY_TO_BACKEND[i];
              const selected = selectedDays.includes(backendDay);
              return (
                <button key={label} type="button"
                  className={`av-day-chip${selected ? " av-day-chip--selected" : ""}`}
                  onClick={() => toggleDay(backendDay)}>
                  {label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Option 2: Monthly */}
      <div className="av-mode-option">
        <label className="av-mode-radio">
          <input type="radio" name="avMode" checked={avMode === "monthly"} onChange={() => setAvMode("monthly")} />
          Avisa sus días cada mes
        </label>
        {avMode === "monthly" && (
          <div className="av-month-grid">
            {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
              <button key={day} type="button"
                className={`av-month-day${selectedDates.includes(day) ? " av-month-day--selected" : ""}`}
                onClick={() => toggleDate(day)}>
                {day}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Option 3: Recurring */}
      <div className="av-mode-option">
        <label className="av-mode-radio">
          <input type="radio" name="avMode" checked={avMode === "recurring"} onChange={() => setAvMode("recurring")} />
          Tiene un día fijo al mes
        </label>
        {avMode === "recurring" && (
          <div className="av-recurring-row">
            <div className="av-recurring-col">
              <span className="av-recurring-label">Día</span>
              {DAY_LABELS.map((label, i) => {
                const backendDay = DAY_TO_BACKEND[i];
                return (
                  <button key={label} type="button"
                    className={`av-recurring-chip${selectedWeekday === backendDay ? " av-recurring-chip--selected" : ""}`}
                    onClick={() => setSelectedWeekday(backendDay)}>
                    {label}
                  </button>
                );
              })}
            </div>
            <div className="av-recurring-col">
              <span className="av-recurring-label">Semana</span>
              {WEEK_LABELS.map((label, i) => (
                <button key={label} type="button"
                  className={`av-recurring-chip${selectedWeekNumber === WEEK_VALUES[i] ? " av-recurring-chip--selected" : ""}`}
                  onClick={() => setSelectedWeekNumber(WEEK_VALUES[i])}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  </fieldset>
</div>
```

- [ ] **Step 3: Update the save handler**

Modify the `handleSubmit` to also call availability API:

```typescript
function handleSubmit(e: FormEvent) {
  e.preventDefault();
  setError("");
  const t = parseInt(target, 10);
  const m = parseInt(max, 10);
  if (isNaN(t) || isNaN(m)) { setError("Meta y máximo deben ser números."); return; }

  // Map avMode to availability_mode
  const availabilityMode = avMode === "monthly" ? "monthly" : "fixed";

  save.mutate({
    name, sex, phone: phone || null, participa_misiones: participaMisiones,
    rank_id: rankId || null,
    availability_mode: availabilityMode,
    monthly_service_target: t, monthly_service_max: m,
    monthly_service_limit_mode: limitMode,
    allowed_area_ids: allowedAreaIds,
  });
}
```

And update the `save` mutation `onSuccess` to call availability API:

```typescript
const save = useMutation({
  mutationFn: (payload: CreateDoctorPayload) =>
    isEdit ? doctorsApi.update(doctor!.id, payload) : doctorsApi.create(payload),
  onSuccess: async (savedDoctor) => {
    const doctorId = savedDoctor.id;
    try {
      if (avMode === "weekly") {
        if (selectedDays.length === 0) { setError("Selecciona al menos un día."); return; }
        await availabilityApi.setWeekly(doctorId, { days_of_week: selectedDays });
      } else if (avMode === "monthly") {
        if (selectedDates.length === 0) { setError("Selecciona al menos un día del mes."); return; }
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
    qc.invalidateQueries({ queryKey: ["doctors"] });
    onClose();
  },
  onError: (err: Error) => setError(err.message),
});
```

Also add the import for `availabilityApi`:

```typescript
import { doctorsApi, availabilityApi, CreateDoctorPayload, DoctorRead } from "../../api/doctors";
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/frontend && npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/doctors/DoctorForm.tsx
git commit -m "feat(doctor): add availability day pickers to DoctorForm"
```

---

### Task 5: Update tests

**Files:**
- Modify: `frontend/src/features/doctors/DoctorForm.test.tsx` (or create if not exists)

- [ ] **Step 1: Check if DoctorForm test exists**

Run: `ls /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/frontend/src/features/doctors/DoctorForm.test.tsx 2>/dev/null || echo "No test file"`

- [ ] **Step 2: If no test file exists, create basic tests**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoctorForm } from "./DoctorForm";
import { availabilityApi } from "../../api/doctors";

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    create: vi.fn().mockResolvedValue({ id: "d1", name: "TEST" }),
    update: vi.fn().mockResolvedValue({ id: "d1", name: "TEST" }),
    listServiceAreas: vi.fn().mockResolvedValue([]),
    listRanks: vi.fn().mockResolvedValue([]),
  },
  availabilityApi: {
    setWeekly: vi.fn().mockResolvedValue({}),
    setMonthly: vi.fn().mockResolvedValue({}),
    setRecurring: vi.fn().mockResolvedValue({}),
  },
}));

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DoctorForm onClose={vi.fn()} />
    </QueryClientProvider>
  );
}

describe("DoctorForm availability", () => {
  it("shows weekly day chips by default", () => {
    renderForm();
    expect(screen.getByText("Trabaja los mismos días todas las semanas")).toBeInTheDocument();
    expect(screen.getByText("Lun")).toBeInTheDocument();
    expect(screen.getByText("Dom")).toBeInTheDocument();
  });

  it("shows monthly grid when monthly option selected", () => {
    renderForm();
    fireEvent.click(screen.getByLabelText("Avisa sus días cada mes"));
    expect(screen.getByText("15")).toBeInTheDocument(); // a day number
  });

  it("shows recurring selectors when recurring option selected", () => {
    renderForm();
    fireEvent.click(screen.getByLabelText("Tiene un día fijo al mes"));
    expect(screen.getByText("Última")).toBeInTheDocument();
  });

  it("calls setWeekly on save with weekly mode", async () => {
    renderForm();
    // Fill required fields
    const nameInput = screen.getByLabelText(/nombre completo/i);
    fireEvent.change(nameInput, { target: { value: "Dr. Test" } });
    // Click a day
    fireEvent.click(screen.getByText("Lun"));
    // Submit
    fireEvent.click(screen.getByText("Guardar"));
    await vi.waitFor(() => {
      expect(availabilityApi.setWeekly).toHaveBeenCalledWith("d1", { days_of_week: [0] });
    });
  });
});
```

- [ ] **Step 3: Run tests to verify**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/frontend && npx vitest run features/doctors/DoctorForm.test.tsx`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/doctors/DoctorForm.test.tsx
git commit -m "test(doctor): add availability form tests"
```

---

### Task 6: Visual verification

**Files:** None (browser check)

- [ ] **Step 1: Start frontend dev server**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/frontend && npx vite --host --port 5173`

- [ ] **Step 2: Start backend**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system && uvicorn backend.app.main:app --host 0.0.0.0 --port 8999`

- [ ] **Step 3: Open browser to http://localhost:5173/doctors and click "Nuevo médico"**

Verify:
- The old "Modo disponibilidad" dropdown is gone
- Radio buttons with clear Spanish labels are visible
- Weekly day chips render and are clickable
- Monthly grid renders when selected
- Recurring selectors render when selected
- Save creates doctor and sets availability
- Edit mode shows existing availability

- [ ] **Step 4: Run full test suite**

Run: `cd /home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system/frontend && npx vitest run`
