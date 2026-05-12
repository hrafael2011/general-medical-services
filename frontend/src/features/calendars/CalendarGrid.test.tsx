// frontend/src/features/calendars/CalendarGrid.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CalendarGrid } from "./CalendarGrid";
import { calendarsApi } from "../../api/calendars";

vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    getGrid: vi.fn().mockResolvedValue({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
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
    list: vi.fn().mockResolvedValue({ items: [{ id: "d1", name: "GARCÍA", service_active: true, rank_id: "r1" }], total: 1 }),
    listRanks: vi.fn().mockResolvedValue([{ id: "r1", name: "cabo", abbreviation: "CABO" }]),
    listServiceAreas: vi.fn().mockResolvedValue([
      { id: "area-1", display_name: "Emergencia", code: "EM", active: true },
      { id: "area-2", display_name: "Pista", code: "PI", active: true },
      { id: "area-3", display_name: "Disponible", code: "DI", active: true },
    ]),
  },
  availabilityApi: {
    availableDoctors: vi.fn().mockResolvedValue([]),
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
    expect(await screen.findByText(/GARCÍA/)).toBeInTheDocument();
  });

  it("muestra el mes y el número de versión", async () => {
    renderGrid();
    expect(await screen.findByText(/mayo 2026.*versión 1/i)).toBeInTheDocument();
  });

  it("muestra botón Generar en modo draft", async () => {
    renderGrid();
    expect(await screen.findByRole("button", { name: /generar/i })).toBeInTheDocument();
  });

  it("renderiza 7 encabezados de día de la semana", async () => {
    renderGrid();
    await screen.findByText("Lun");
    const headers = screen.getAllByText(/^(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)$/);
    expect(headers).toHaveLength(7);
  });

  it("muestra el día 1 en la posición correcta (viernes, columna 5)", async () => {
    const { container } = renderGrid();
    await screen.findByText("1");
    const grid = container.querySelector(".calendar-grid");
    // May 1, 2026 is Friday; Monday-first offset = 4 (column index 4, 0-based)
    // In flat layout: 7 headers (idx 0-6) + 4 padding cells (idx 7-10) + May 1 cell = idx 11
    expect(grid?.children[11]?.querySelector(".calendar-day-number")?.textContent).toBe("1");
  });

  it("muestra las áreas con colores correctos", async () => {
    const { container } = renderGrid();
    await screen.findByText("1");
    const dots = container.querySelectorAll(".calendar-area-dot");
    expect(dots.length).toBeGreaterThan(0);
    // Areas are sorted alphabetically: Disponible (green), Emergencia (red), Pista (blue)
    expect(dots[0].getAttribute("style")).toMatch(/#16a34a|rgb\(22,\s*163,\s*74\)/);
    expect(dots[1].getAttribute("style")).toMatch(/#dc2626|rgb\(220,\s*38,\s*38\)/);
    expect(dots[2].getAttribute("style")).toMatch(/#2563eb|rgb\(37,\s*99,\s*235\)/);
  });

  it("muestra '— — —' para áreas vacías en modo draft", async () => {
    renderGrid();
    // Multiple cells have empty areas → "— — —" appears many times
    const dashes = await screen.findAllByText("— — —");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("muestra '+ Asignar' en modo draft", async () => {
    renderGrid();
    const assignLinks = await screen.findAllByText("+ Asignar");
    expect(assignLinks.length).toBeGreaterThan(0);
  });

  it("muestra celdas vacías cuando no hay slots en modo draft", async () => {
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();
    await screen.findByText(/mayo 2026/i);
    // All areas are empty → "— — —" for all area rows
    const dashes = await screen.findAllByText("— — —");
    expect(dashes.length).toBeGreaterThan(0);
    // "+ Asignar" still visible in draft even with no slots
    expect(screen.getAllByText("+ Asignar").length).toBeGreaterThan(0);
  });

  it("no muestra enlaces de asignación en modo aprobado", async () => {
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "approved", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();
    await screen.findByText(/mayo 2026/i);
    expect(screen.queryByText("+ Asignar")).not.toBeInTheDocument();
    expect(screen.queryByText("— — —")).not.toBeInTheDocument();
    // Approved mode shows single "—" for empty areas
    const dashes = await screen.findAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
    // "Nueva versión" button replaces "Generar" in approved mode
    expect(screen.getByRole("button", { name: /nueva versión/i })).toBeInTheDocument();
  });
});
