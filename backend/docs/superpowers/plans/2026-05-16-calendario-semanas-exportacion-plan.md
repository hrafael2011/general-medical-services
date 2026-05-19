# Frontend: Weeks Panel + PDF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add week-level approve/unlock UI and PDF export buttons to CalendarGrid, plus the corresponding API client functions.

**Architecture:** Three frontend-only changes: (1) new types + functions in `calendars.ts` API client, (2) week panel + export buttons in `CalendarGrid.tsx`, (3) tests for both. The backend endpoints already exist and are deployed.

**Tech Stack:** React 18, TypeScript, TanStack Query, Vitest + React Testing Library

---

### Task 1: Add WeekRead type and week/PDF API functions to calendars.ts

**Files:**
- Modify: `frontend/src/api/calendars.ts`

- [ ] **Step 1: Add WeekRead type after CalendarGridResponse (after line 74)**

```typescript
export interface WeekRead {
  id: string;
  week_number: number;
  label: string;
  start_date: string;
  end_date: string;
  status: string;
  assignment_count: number;
  approved_by: string | null;
  approved_at: string | null;
}
```

- [ ] **Step 2: Add 5 new API functions to calendarsApi object (after the `delete` function)**

```typescript
  listWeeks: (calendarId: string) =>
    apiFetch<WeekRead[]>(`/calendars/${calendarId}/weeks`),

  approveWeek: (calendarId: string, weekId: string) =>
    apiFetch<WeekRead>(`/calendars/${calendarId}/weeks/${weekId}/approve`, {
      method: "POST",
    }),

  unlockWeek: (calendarId: string, weekId: string) =>
    apiFetch<WeekRead>(`/calendars/${calendarId}/weeks/${weekId}/unlock`, {
      method: "POST",
    }),

  exportWeeklyPDF: (calendarId: string, weekId: string) =>
    apiFetch<Blob>(
      `/reports/calendar/${calendarId}/weeks/${weekId}/pdf`,
      {},
      "blob",
    ),

  exportFullCalendarPDF: (calendarId: string) =>
    apiFetch<Blob>(
      `/reports/calendar/${calendarId}/full-pdf`,
      {},
      "blob",
    ),
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -5`
Expected: No new errors from our changes.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/api/calendars.ts && git commit -m "feat: add WeekRead type and week/export API functions"
```

---

### Task 2: Add week panel and PDF export buttons to CalendarGrid

**Files:**
- Modify: `frontend/src/features/calendars/CalendarGrid.tsx`

- [ ] **Step 1: Update icon import (line 5)**

Change:
```typescript
import { CheckCircle2, Trash2, Wand2 } from "lucide-react";
```
To:
```typescript
import { CheckCircle2, Download, FileDown, Trash2, Wand2 } from "lucide-react";
```

- [ ] **Step 2: Update API import (line 6)**

Change:
```typescript
import { calendarsApi, CalendarAssignmentRead, DaySlot } from "../../api/calendars";
```
To:
```typescript
import { calendarsApi, CalendarAssignmentRead, DaySlot, WeekRead } from "../../api/calendars";
```

- [ ] **Step 3: Add weeks query and mutation hooks**  
Insert after the `availableDoctorIds` query block, before the `if (!calendarId)` check:

```typescript
  const { data: weeks = [] } = useQuery({
    queryKey: ["calendar-weeks", calendarId],
    queryFn: () => calendarsApi.listWeeks(calendarId!),
    enabled: !!calendarId,
  });

  const approveWeekMutation = useMutation({
    mutationFn: (weekId: string) => calendarsApi.approveWeek(calendarId!, weekId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendar-weeks", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Semana aprobada.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al aprobar semana."),
  });

  const unlockWeekMutation = useMutation({
    mutationFn: (weekId: string) => calendarsApi.unlockWeek(calendarId!, weekId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendar-weeks", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Semana desbloqueada.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al desbloquear semana."),
  });

  const handleExportWeeklyPDF = async (weekId: string) => {
    try {
      const blob = await calendarsApi.exportWeeklyPDF(calendarId!, weekId);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (err) {
      addToast("error", err instanceof ApiError ? err.message : "Error al exportar PDF semanal.");
    }
  };

  const handleExportFullCalendarPDF = async () => {
    try {
      const blob = await calendarsApi.exportFullCalendarPDF(calendarId!);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (err) {
      addToast("error", err instanceof ApiError ? err.message : "Error al exportar PDF del calendario.");
    }
  };
```

- [ ] **Step 4: Add week panel UI**  
Insert after the gap warning block, before `{assignTarget && ...}`:

```tsx
      {/* Week panel */}
      {weeks.length > 0 && (
        <div style={{ marginTop: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>Semanas</h3>
            <button
              className="btn-ghost"
              onClick={handleExportFullCalendarPDF}
              title="Exportar calendario completo en PDF"
            >
              <FileDown size={15} /> Calendario completo PDF
            </button>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e0e0e0", textAlign: "left" }}>
                <th style={{ padding: "0.4rem 0.5rem" }}>Semana</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Rango</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Asignaciones</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Estado</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((w: WeekRead) => (
                <tr key={w.id} style={{ borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: "0.4rem 0.5rem", fontWeight: 600 }}>
                    {w.label}
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem", color: "#555" }}>
                    {w.start_date} → {w.end_date}
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem" }}>
                    {w.assignment_count}
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem" }}>
                    <span style={{
                      display: "inline-block",
                      padding: "2px 8px",
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 700,
                      background: w.status === "approved" ? "#d1fae5" : "#f3f4f6",
                      color: w.status === "approved" ? "#065f46" : "#6b7280",
                    }}>
                      {w.status === "approved" ? "Aprobada" : "Borrador"}
                    </span>
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    {w.status === "draft" && isDraft && (
                      <button
                        className="btn-primary"
                        style={{ fontSize: 12, padding: "2px 10px" }}
                        disabled={approveWeekMutation.isPending}
                        onClick={() => approveWeekMutation.mutate(w.id)}
                      >
                        <CheckCircle2 size={13} /> Aprobar
                      </button>
                    )}
                    {w.status === "approved" && (
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 12, padding: "2px 10px" }}
                        disabled={unlockWeekMutation.isPending}
                        onClick={() => unlockWeekMutation.mutate(w.id)}
                      >
                        Desbloquear
                      </button>
                    )}
                    {w.status === "approved" && (
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 12, padding: "2px 10px" }}
                        onClick={() => handleExportWeeklyPDF(w.id)}
                        title="Exportar lista semanal en PDF"
                      >
                        <Download size={13} /> PDF
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
```

- [ ] **Step 5: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -5`
Expected: No new errors.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/features/calendars/CalendarGrid.tsx && git commit -m "feat: add week panel with approve/unlock and PDF export buttons"
```

---

### Task 3: Add tests for week panel and export buttons

**Files:**
- Modify: `frontend/src/features/calendars/CalendarGrid.test.tsx`

- [ ] **Step 1: Replace the entire `vi.mock("../../api/calendars", ...)` block with updated mock that includes `listWeeks`, `approveWeek`, `unlockWeek`, `exportWeeklyPDF`, `exportFullCalendarPDF`**

```typescript
vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    getGrid: vi.fn().mockResolvedValue({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
      slots: [
        { service_date: "2026-05-01", service_area_id: "area-1", assignment: { id: "a1", doctor_id: "d1", assignment_source: "generated", rationale: null, override_justification: null, created_by: null, created_at: "", calendar_version_id: "v1", service_date: "2026-05-01", service_area_id: "area-1" }, has_warning: false, warning_message: null },
      ],
      gaps: [],
    }),
    listWeeks: vi.fn().mockResolvedValue([
      { id: "w1", week_number: 1, label: "Semana 1 (Abr 27 - May 3)", start_date: "2026-04-27", end_date: "2026-05-03", status: "approved", assignment_count: 5, approved_by: null, approved_at: null },
      { id: "w2", week_number: 2, label: "Semana 2 (May 4 - May 10)", start_date: "2026-05-04", end_date: "2026-05-10", status: "approved", assignment_count: 4, approved_by: null, approved_at: null },
      { id: "w3", week_number: 3, label: "Semana 3 (May 11 - May 17)", start_date: "2026-05-11", end_date: "2026-05-17", status: "draft", assignment_count: 3, approved_by: null, approved_at: null },
      { id: "w4", week_number: 4, label: "Semana 4 (May 18 - May 24)", start_date: "2026-05-18", end_date: "2026-05-24", status: "draft", assignment_count: 2, approved_by: null, approved_at: null },
      { id: "w5", week_number: 5, label: "Semana 5 (May 25 - May 31)", start_date: "2026-05-25", end_date: "2026-05-31", status: "draft", assignment_count: 0, approved_by: null, approved_at: null },
    ]),
    approveWeek: vi.fn(),
    unlockWeek: vi.fn(),
    exportWeeklyPDF: vi.fn().mockResolvedValue(new Blob()),
    exportFullCalendarPDF: vi.fn().mockResolvedValue(new Blob()),
    generate: vi.fn(),
    approve: vi.fn(),
    unlock: vi.fn(),
    assignDoctor: vi.fn(),
    removeAssignment: vi.fn(),
  },
}));
```

- [ ] **Step 2: Add 9 new test cases at end of the `describe("CalendarGrid", ...)` block**

```typescript
  it("muestra el panel de semanas con 5 semanas", async () => {
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    expect(screen.getByText(/Semana 1/)).toBeInTheDocument();
    expect(screen.getByText(/Semana 5/)).toBeInTheDocument();
  });

  it("muestra estados aprobada/borrador correctamente", async () => {
    renderGrid();
    await screen.findByText("Semanas");
    const approvedBadges = screen.getAllByText("Aprobada");
    const draftBadges = screen.getAllByText("Borrador");
    expect(approvedBadges).toHaveLength(2);
    expect(draftBadges).toHaveLength(3);
  });

  it("muestra conteo de asignaciones por semana", async () => {
    renderGrid();
    await screen.findByText("Semanas");
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("muestra botón Aprobar en semanas draft cuando el calendario es draft", async () => {
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    const approveButtons = screen.getAllByRole("button", { name: /aprobar/i });
    expect(approveButtons.length).toBeGreaterThanOrEqual(3);
  });

  it("muestra botón PDF solo en semanas aprobadas", async () => {
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    const pdfButtons = screen.getAllByTitle("Exportar lista semanal en PDF");
    expect(pdfButtons).toHaveLength(2);
  });

  it("muestra botón de exportar calendario completo PDF", async () => {
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    expect(screen.getByTitle("Exportar calendario completo en PDF")).toBeInTheDocument();
  });

  it("llama a exportWeeklyPDF al clickear botón PDF de semana", async () => {
    const { calendarsApi } = await import("../../api/calendars");
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    const pdfButtons = screen.getAllByTitle("Exportar lista semanal en PDF");
    pdfButtons[0].click();
    expect(calendarsApi.exportWeeklyPDF).toHaveBeenCalledWith("c1", "w1");
  });

  it("llama a exportFullCalendarPDF al clickear botón de calendario completo", async () => {
    const { calendarsApi } = await import("../../api/calendars");
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    screen.getByTitle("Exportar calendario completo en PDF").click();
    expect(calendarsApi.exportFullCalendarPDF).toHaveBeenCalledWith("c1");
  });

  it("no muestra botones de aprobar semana si el calendario está aprobado", async () => {
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "approved", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "approved", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    const approveButtons = screen.queryAllByRole("button", { name: /aprobar/i });
    expect(approveButtons).toHaveLength(0);
  });
```

- [ ] **Step 3: Run the CalendarGrid tests**

Run: `cd frontend && npx vitest run src/features/calendars/CalendarGrid.test.tsx 2>&1 | tail -20`
Expected: All tests (8 existing + 9 new = 17 total) PASS.

- [ ] **Step 4: Run full frontend test suite**

Run: `cd frontend && npx vitest run 2>&1 | tail -10`
Expected: All tests pass, no regressions.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/features/calendars/CalendarGrid.test.tsx && git commit -m "test: add week panel and PDF export tests"
```

---

### Backend Endpoints Consumed

| Endpoint | Method | Used By |
|----------|--------|---------|
| `/api/calendars/{id}/weeks` | GET | `listWeeks()` |
| `/api/calendars/{id}/weeks/{week_id}/approve` | POST | `approveWeek()` |
| `/api/calendars/{id}/weeks/{week_id}/unlock` | POST | `unlockWeek()` |
| `/api/reports/calendar/{id}/weeks/{week_id}/pdf` | GET | `exportWeeklyPDF()` |
| `/api/reports/calendar/{id}/full-pdf` | GET | `exportFullCalendarPDF()` |
