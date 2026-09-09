import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, it, expect, vi } from "vitest";
import { AssignDoctorModal } from "./AssignDoctorModal";
import { calendarsApi, EligibleDoctorRead } from "../../api/calendars";

// Mock the API module
vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    eligibleDoctors: vi.fn(),
    evaluate: vi.fn(),
  },
  // Re-export types so the import works
  EligibleDoctorRead: {},
  UnavailableDoctorRead: {},
  WarningItem: {},
}));

const ELIGIBLE_DOCTORS: EligibleDoctorRead[] = [
  { id: "d1", full_name: "Dr. García Martínez", specialty: "General", rank_name: "Capitán", altera_orden: false },
  { id: "d2", full_name: "Dr. López Ruiz", specialty: "Cirugía", rank_name: "Mayor", altera_orden: true },
  { id: "d3", full_name: "Dra. Torres", specialty: "Pediatría", rank_name: "Teniente", altera_orden: null },
];

const BASE_PROPS = {
  calendarId: "cal-1",
  versionId: "ver-1",
  date: "2026-05-03",
  areaId: "area-1",
  areaName: "Emergencia",
  onConfirm: vi.fn(),
  onClose: vi.fn(),
  isLoading: false,
};

describe("AssignDoctorModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({ doctors: ELIGIBLE_DOCTORS, unavailable: [] });
  });

  it("muestra la fecha y área en el título", async () => {
    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText(/3 de mayo.*emergencia/i)).toBeInTheDocument();
    });
  });

  it("lista los doctores disponibles después de cargar", async () => {
    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    expect(screen.getByText("Dr. López Ruiz")).toBeInTheDocument();
    expect(screen.getByText("Dra. Torres")).toBeInTheDocument();
  });

  it("muestra 'Cargando doctores disponibles…' mientras carga", () => {
    // Resolve never to keep loading state
    vi.mocked(calendarsApi.eligibleDoctors).mockImplementation(() => new Promise(() => {}));
    render(<AssignDoctorModal {...BASE_PROPS} />);
    expect(screen.getByText(/cargando doctores disponibles/i)).toBeInTheDocument();
  });

  it("muestra mensaje cuando no hay médicos para asignar", async () => {
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({ doctors: [], unavailable: [] });
    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText(/no hay médicos para asignar/i)).toBeInTheDocument();
    });
  });

  it("filtra por nombre al escribir en el buscador", async () => {
    const user = userEvent.setup();
    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText(/buscar/i), "García");
    expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    expect(screen.queryByText("Dr. López Ruiz")).not.toBeInTheDocument();
  });

  it("llama onConfirm directamente cuando no hay hard_blocks ni warnings", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    vi.mocked(calendarsApi.evaluate).mockResolvedValue({ hard_blocks: [], warnings: [] });

    render(<AssignDoctorModal {...BASE_PROPS} onConfirm={onConfirm} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Dr. García Martínez"));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith("d1", [], "");
    });
  });

  it("muestra error cuando hay hard_blocks", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    vi.mocked(calendarsApi.evaluate).mockResolvedValue({
      hard_blocks: [{ code: "max_per_month", description: "Límite mensual alcanzado." }],
      warnings: [],
    });

    render(<AssignDoctorModal {...BASE_PROPS} onConfirm={onConfirm} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Dr. García Martínez"));
    await waitFor(() => {
      expect(screen.getByText(/Límite mensual alcanzado/i)).toBeInTheDocument();
    });
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("muestra pantalla de revisión de advertencias cuando hay warnings", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    vi.mocked(calendarsApi.evaluate).mockResolvedValue({
      hard_blocks: [],
      warnings: [{ code: "weekly_overload", description: "Excede carga semanal." }],
    });

    render(<AssignDoctorModal {...BASE_PROPS} onConfirm={onConfirm} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Dr. García Martínez"));
    await waitFor(() => {
      expect(screen.getByText(/Advertencias de reglas/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Excede carga semanal/i)).toBeInTheDocument();
    // Button disabled until all warnings are checked
    expect(screen.getByRole("button", { name: /asignar con advertencias/i })).toBeDisabled();

    // Check the warning checkbox — button enables (justificación opcional)
    await user.click(screen.getByText(/Excede carga semanal/i));
    const confirmBtn = screen.getByRole("button", { name: /asignar con advertencias/i });
    expect(confirmBtn).toBeEnabled();

    // Confirmar sin justificación → onConfirm con justificación vacía
    await user.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledWith("d1", ["weekly_overload"], "");
  });

  it("lista con motivo clicable: al elegirlo se evalúa y salen advertencias", async () => {
    const user = userEvent.setup();
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({
      doctors: [],
      unavailable: [
        { doctor_id: "d9", full_name: "Dr. Oculto", code: "no_availability", description: "No tiene disponibilidad para esta fecha.", is_hard: false },
      ],
    });
    vi.mocked(calendarsApi.evaluate).mockResolvedValue({
      hard_blocks: [],
      warnings: [{ code: "no_availability", description: "No tiene disponibilidad para esta fecha." }],
    });

    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText(/Dr\. Oculto/)).toBeInTheDocument();
    });
    expect(screen.getByText(/No tiene disponibilidad para esta fecha/)).toBeInTheDocument();
    // La fila entera es clicable (ya no hay botón "Evaluar de todas formas")
    expect(screen.queryByRole("button", { name: /evaluar de todas formas/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Dr\. Oculto/i }));
    await waitFor(() => {
      expect(calendarsApi.evaluate).toHaveBeenCalledWith("cal-1", {
        doctor_id: "d9", service_date: "2026-05-03", service_area_id: "area-1",
        replacing_assignment_id: null,
      });
    });
    expect(await screen.findByText(/Advertencias de reglas/i)).toBeInTheDocument();
  });

  it("muestra médicos con bloqueo duro: visibles pero sin clic", async () => {
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({
      doctors: [],
      unavailable: [
        { doctor_id: "d8", full_name: "Dr. Inactivo", code: "doctor_inactive", description: "El médico no está activo o no tiene servicio activo.", is_hard: true },
      ],
    });

    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText(/Dr\. Inactivo/)).toBeInTheDocument();
    });
    expect(screen.getByText(/no está activo/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Dr\. Inactivo/i })).not.toBeInTheDocument();
  });

  it("llama onClose al hacer clic en Cancelar", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<AssignDoctorModal {...BASE_PROPS} onClose={onClose} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("llama onRemove al hacer clic en Quitar asignación", async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();
    render(<AssignDoctorModal {...BASE_PROPS} onRemove={onRemove} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /quitar asignación/i }));
    expect(onRemove).toHaveBeenCalled();
  });

  it("el interruptor de otros días recarga con strict=false y muestra fuera-de-día", async () => {
    const user = userEvent.setup();
    const { calendarsApi } = await import("../../api/calendars");
    const eligibleDoctors = vi.mocked(calendarsApi.eligibleDoctors);
    eligibleDoctors.mockImplementation(async (_cal, _date, _area, strict = true) =>
      strict
        ? { doctors: ELIGIBLE_DOCTORS, unavailable: [] }
        : {
            doctors: [],
            unavailable: [
              { doctor_id: "d9", full_name: "Dr. Fuera Día", code: "no_availability", description: "No tiene disponibilidad para esta fecha.", is_hard: false, outside_pattern: true },
            ],
          }
    );

    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    // Por defecto consulta en modo estricto (solo los del día)
    expect(eligibleDoctors).toHaveBeenLastCalledWith("cal-1", "2026-05-03", "area-1", true);

    // Activar el interruptor (switch) → recarga con strict=false y lista al fuera-de-día
    await user.click(screen.getByRole("switch", { name: /no son de este día/i }));
    await waitFor(() => {
      expect(eligibleDoctors).toHaveBeenLastCalledWith("cal-1", "2026-05-03", "area-1", false);
    });
    expect(await screen.findByText("Dr. Fuera Día")).toBeInTheDocument();
    expect(screen.getByText(/No es de este día/i)).toBeInTheDocument();
  });

  it("el buscador encuentra médicos con motivo y los disponibles van primero", async () => {
    const user = userEvent.setup();
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({
      doctors: ELIGIBLE_DOCTORS,
      unavailable: [
        { doctor_id: "d9", full_name: "Dr. Oculto", code: "no_availability", description: "Sin disponibilidad para esta fecha.", is_hard: false },
        { doctor_id: "d8", full_name: "Dr. Inactivo", code: "doctor_inactive", description: "Inactivo.", is_hard: true },
      ],
    });

    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    });
    await screen.findByText(/Dr\. Oculto/);

    // Orden: los disponibles del día primero, los de otros días después
    const buttons = screen.getAllByRole("button").map(b => b.textContent ?? "");
    const garcia = buttons.findIndex(t => t.includes("García"));
    const oculto = buttons.findIndex(t => t.includes("Oculto"));
    expect(garcia).toBeGreaterThanOrEqual(0);
    expect(oculto).toBeGreaterThan(garcia);

    // El buscador filtra TODA la lista (no solo los del día)
    await user.type(screen.getByPlaceholderText(/buscar/i), "oculto");
    expect(screen.queryByText("Dr. García Martínez")).not.toBeInTheDocument();
    expect(screen.getByText(/Dr\. Oculto/)).toBeInTheDocument();
    // El bloqueado sigue visible (atenuado, sin clic) al coincidir con "inacti"
    await user.clear(screen.getByPlaceholderText(/buscar/i));
    await user.type(screen.getByPlaceholderText(/buscar/i), "inactivo");
    expect(screen.getByText(/Dr\. Inactivo/)).toBeInTheDocument();
  });
});
