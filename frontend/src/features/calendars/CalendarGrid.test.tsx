// frontend/src/features/calendars/CalendarGrid.test.tsx
import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CalendarGrid } from "./CalendarGrid";
import { calendarsApi } from "../../api/calendars";

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
      { id: "w1", week_number: 1, label: "Semana 1 (Abr 26 - May 2)", start_date: "2026-04-26", end_date: "2026-05-02", status: "approved", assignment_count: 5, approved_by: null, approved_at: null, doctor_assignment_counts: [{ doctor_id: "d1", doctor_name: "GARCÍA", count: 2 }] },
      { id: "w2", week_number: 2, label: "Semana 2 (May 3 - May 9)", start_date: "2026-05-03", end_date: "2026-05-09", status: "approved", assignment_count: 4, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
      { id: "w3", week_number: 3, label: "Semana 3 (May 10 - May 16)", start_date: "2026-05-10", end_date: "2026-05-16", status: "draft", assignment_count: 3, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
      { id: "w4", week_number: 4, label: "Semana 4 (May 17 - May 23)", start_date: "2026-05-17", end_date: "2026-05-23", status: "draft", assignment_count: 2, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
      { id: "w5", week_number: 5, label: "Semana 5 (May 24 - May 30)", start_date: "2026-05-24", end_date: "2026-05-30", status: "draft", assignment_count: 0, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
      { id: "w6", week_number: 6, label: "Semana 6 (May 31 - Jun 6)", start_date: "2026-05-31", end_date: "2026-06-06", status: "draft", assignment_count: 0, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
    ]),
    approveWeek: vi.fn(),
    unlockWeek: vi.fn(),
    exportWeeklyPDF: vi.fn().mockResolvedValue(new Blob()),
    exportFullCalendarPDF: vi.fn().mockResolvedValue(new Blob()),
    generate: vi.fn().mockResolvedValue({
      version_id: "v1",
      calendar_id: "c1",
      month: 5,
      year: 2026,
      calendar_status: "draft",
      generation_mode: "assisted_auto",
      review_required: true,
      total_slots: 10,
      assigned_count: 8,
      gap_count: 2,
      slots: [],
    }),
    approve: vi.fn(),
    unlock: vi.fn(),
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

beforeEach(() => {
  vi.clearAllMocks();
});

const allDraftWeeks = [
  { id: "w1", week_number: 1, label: "Semana 1 (Abr 26 - May 2)", start_date: "2026-04-26", end_date: "2026-05-02", status: "draft", assignment_count: 5, approved_by: null, approved_at: null, doctor_assignment_counts: [{ doctor_id: "d1", doctor_name: "GARCÍA", count: 2 }] },
  { id: "w2", week_number: 2, label: "Semana 2 (May 3 - May 9)", start_date: "2026-05-03", end_date: "2026-05-09", status: "draft", assignment_count: 4, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
  { id: "w3", week_number: 3, label: "Semana 3 (May 10 - May 16)", start_date: "2026-05-10", end_date: "2026-05-16", status: "draft", assignment_count: 3, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
  { id: "w4", week_number: 4, label: "Semana 4 (May 17 - May 23)", start_date: "2026-05-17", end_date: "2026-05-23", status: "draft", assignment_count: 2, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
  { id: "w5", week_number: 5, label: "Semana 5 (May 24 - May 30)", start_date: "2026-05-24", end_date: "2026-05-30", status: "draft", assignment_count: 0, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
  { id: "w6", week_number: 6, label: "Semana 6 (May 31 - Jun 6)", start_date: "2026-05-31", end_date: "2026-06-06", status: "draft", assignment_count: 0, approved_by: null, approved_at: null, doctor_assignment_counts: [] },
];

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
    expect((await screen.findAllByText(/GARCÍA/)).length).toBeGreaterThan(0);
  });

  it("muestra el mes y el número de versión", async () => {
    renderGrid();
    expect(await screen.findByText(/mayo 2026.*versión 1/i)).toBeInTheDocument();
  });

  it("muestra botón Generar calendario con reglas en modo draft", async () => {
    vi.mocked(calendarsApi.listWeeks).mockResolvedValueOnce(allDraftWeeks);
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();
    expect(await screen.findByRole("button", { name: /generar calendario con reglas/i })).toBeInTheDocument();
  });

  it("refresca semanas después de generar con reglas", async () => {
    const { calendarsApi } = await import("../../api/calendars");
    const userEvent = await import("@testing-library/user-event");
    vi.mocked(calendarsApi.listWeeks).mockResolvedValueOnce(allDraftWeeks);
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();

    await screen.findByText("Semanas");
    expect(calendarsApi.listWeeks).toHaveBeenCalledTimes(1);

    await userEvent.default.click(
      screen.getByRole("button", { name: /generar calendario con reglas/i }),
    );

    await waitFor(() => {
      expect(calendarsApi.generate).toHaveBeenCalledWith("c1");
      expect(calendarsApi.listWeeks).toHaveBeenCalledTimes(2);
    });
  });

  it("oculta generación con reglas si existe una semana aprobada", async () => {
    renderGrid();
    await screen.findByText("Semanas");
    expect(screen.queryByRole("button", { name: /generar calendario con reglas/i })).not.toBeInTheDocument();
  });

  it("renderiza 7 encabezados de día de la semana", async () => {
    renderGrid();
    await screen.findByText("Lun");
    const headers = screen.getAllByText(/^(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)$/);
    expect(headers).toHaveLength(7);
  });

  it("muestra el día 1 en la posición correcta (viernes, columna 6)", async () => {
    const { container } = renderGrid();
    await screen.findByText("1");
    const grid = container.querySelector(".calendar-grid");
    // May 1, 2026 is Friday; Sunday-first offset = 5 (column index 5, 0-based)
    // In flat layout: 7 headers (idx 0-6) + 5 days before May 1 (idx 7-11) + May 1 = idx 12
    expect(grid?.children[12]?.querySelector(".calendar-day-number")?.textContent).toBe("1");
  });

  it("etiqueta los días de otro mes en semanas cruzadas", async () => {
    const { container } = renderGrid();
    await screen.findByText("abr 26");
    const grid = container.querySelector(".calendar-grid");
    // First cell after headers (index 7) is Sun Apr 26 (outside-month)
    expect(grid?.children[7]?.querySelector(".calendar-day-number")?.textContent).toBe("abr 26");
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

  it("muestra '+ Asignar médico' en áreas vacías en modo draft", async () => {
    renderGrid();
    const assignLabels = await screen.findAllByText("+ Asignar médico");
    expect(assignLabels.length).toBeGreaterThan(0);
  });

  it("no permite asignar dentro de una semana aprobada aunque la versión esté en borrador", async () => {
    const { container } = renderGrid();
    await screen.findByText("Semanas");
    const grid = container.querySelector(".calendar-grid");
    // May 1 is at index 12 in the new Sun-Sat layout (7 headers + 5 outside-month days)
    const mayFirstCell = grid?.children[12] as HTMLElement;

    expect(within(mayFirstCell).queryByText("+ Asignar médico")).not.toBeInTheDocument();
    expect(within(mayFirstCell).getByText(/GARCÍA/)).toBeInTheDocument();
  });

  it("muestra celdas vacías cuando no hay slots en modo draft", async () => {
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();
    await screen.findByText(/mayo 2026/i);
    // All slots empty → "+ Asignar médico" in all area rows
    const assignLabels = await screen.findAllByText("+ Asignar médico");
    expect(assignLabels.length).toBeGreaterThan(0);
  });

  it("no muestra generación ni edición global en modo aprobado", async () => {
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "draft", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "approved", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });
    renderGrid();
    await screen.findByText(/mayo 2026/i);
    expect(screen.queryByText("+ Asignar médico")).not.toBeInTheDocument();
    // Approved mode shows single "—" for empty areas
    const dashes = await screen.findAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /generar calendario con reglas/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar calendario/i })).not.toBeInTheDocument();
  });

  it("muestra estado parcial cuando solo algunas semanas están aprobadas", async () => {
    vi.mocked(calendarsApi.getGrid).mockResolvedValueOnce({
      calendar: { id: "c1", year: 2026, month: 5, status: "partial", generation_mode: "manual", created_by: null, approved_by: null, created_at: "", updated_at: "", approved_at: null },
      version: { id: "v1", calendar_id: "c1", version_number: 1, status: "draft", created_by: null, reason: null, created_at: "" },
      slots: [],
      gaps: [],
    });

    renderGrid();

    expect(await screen.findByText("Parcial")).toBeInTheDocument();
  });

  it("muestra el panel de semanas con 6 semanas", async () => {
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    expect(screen.getByText(/Semana 1/)).toBeInTheDocument();
    expect(screen.getByText(/Semana 6/)).toBeInTheDocument();
  });

  it("muestra estados aprobada/borrador correctamente", async () => {
    renderGrid();
    await screen.findByText("Semanas");
    const approvedBadges = screen.getAllByText("Aprobada");
    const draftBadges = screen.getAllByText("Borrador");
    expect(approvedBadges).toHaveLength(2);
    // 4 week-level Borrador badges + 1 calendar-level Borrador badge = 5
    expect(draftBadges).toHaveLength(5);
  });

  it("muestra conteo de asignaciones por semana", async () => {
    renderGrid();
    await screen.findByText("Semanas");
    // "5" and "4" appear as both day numbers and week assignment counts
    expect(screen.getAllByText("5").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("4").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(1);
  });

  it("no muestra nombres de médicos en la columna de asignaciones semanales", async () => {
    renderGrid();
    await screen.findByText("Semanas");
    expect(screen.queryByText("GARCÍA × 2")).not.toBeInTheDocument();
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
    await waitFor(() => {
      expect(calendarsApi.exportWeeklyPDF).toHaveBeenCalledWith("c1", "w1");
    });
  });

  it("llama a exportFullCalendarPDF al clickear botón de calendario completo", async () => {
    const { calendarsApi } = await import("../../api/calendars");
    renderGrid();
    expect(await screen.findByText("Semanas")).toBeInTheDocument();
    screen.getByTitle("Exportar calendario completo en PDF").click();
    await waitFor(() => {
      expect(calendarsApi.exportFullCalendarPDF).toHaveBeenCalledWith("c1");
    });
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
});
