// frontend/src/features/calendars/CalendarGrid.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CalendarGrid } from "./CalendarGrid";

vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    getGrid: vi.fn().mockResolvedValue({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft" },
      version: { id: "v1", version_number: 1, status: "draft" },
      slots: [
        { service_date: "2026-05-01", service_area_id: "area-1", assignment: { id: "a1", doctor_id: "d1", assignment_source: "generated", rationale: null, override_justification: null, created_by: null, created_at: "", calendar_version_id: "v1", service_date: "2026-05-01", service_area_id: "area-1" }, has_warning: false, warning_message: null },
      ],
      gaps: [],
    }),
    generate: vi.fn(),
    approve: vi.fn(),
    newVersion: vi.fn(),
    assignDoctor: vi.fn(),
    removeAssignment: vi.fn(),
  },
}));

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: vi.fn().mockResolvedValue({ items: [{ id: "d1", name: "Dr. García", service_active: true }], total: 1 }),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function renderGrid() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/calendars/c1"]}>
      <QueryClientProvider client={qc}>
        <Routes>
          <Route path="/calendars/:calendarId" element={<CalendarGrid />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("CalendarGrid", () => {
  it("muestra el nombre del médico en lugar del UUID", async () => {
    renderGrid();
    expect(await screen.findByText("García")).toBeInTheDocument();
  });

  it("muestra el mes y el número de versión", async () => {
    renderGrid();
    expect(await screen.findByText(/mayo 2026.*versión 1/i)).toBeInTheDocument();
  });

  it("muestra botón Generar en modo draft", async () => {
    renderGrid();
    expect(await screen.findByRole("button", { name: /generar/i })).toBeInTheDocument();
  });
});
