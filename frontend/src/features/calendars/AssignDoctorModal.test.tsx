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
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({ doctors: ELIGIBLE_DOCTORS });
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

  it("muestra mensaje cuando no hay doctores disponibles", async () => {
    vi.mocked(calendarsApi.eligibleDoctors).mockResolvedValue({ doctors: [] });
    render(<AssignDoctorModal {...BASE_PROPS} />);
    await waitFor(() => {
      expect(screen.getByText(/no hay doctores disponibles/i)).toBeInTheDocument();
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
      expect(onConfirm).toHaveBeenCalledWith("d1", []);
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
    // Button should be disabled until all warnings are checked
    expect(screen.getByRole("button", { name: /asignar con advertencias/i })).toBeDisabled();

    // Check the warning checkbox
    await user.click(screen.getByText(/Excede carga semanal/i));
    expect(screen.getByRole("button", { name: /asignar con advertencias/i })).toBeEnabled();

    // Click confirm
    await user.click(screen.getByRole("button", { name: /asignar con advertencias/i }));
    expect(onConfirm).toHaveBeenCalledWith("d1", ["weekly_overload"]);
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
});
