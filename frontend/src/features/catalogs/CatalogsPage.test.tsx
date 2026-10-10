import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../components/Toast";
import { CatalogsPage } from "./CatalogsPage";

const mockCreateDeactivationReason = vi.fn().mockResolvedValue({
  id: "reason-new",
  code: "capacitacion",
  display_name: "Capacitación",
  active: true,
  requires_detail: false,
  applies_to_sex: null,
  severity: "hard_block",
  expects_return: true,
});
const mockUpdateRank = vi.fn().mockResolvedValue({});
const mockUpdateDeactivationReason = vi.fn().mockResolvedValue({});

const { SIGNATURES, mockSaveReportSignatures } = vi.hoisted(() => {
  const signatures = {
    left_title1: "Sargento Médico FARD.",
    left_title2: "Encargada de los Servicios de los Médicos Generales",
    left_title3: 'del Hosp. Mil. Univ. Doc. FARD, "DRL".',
    right_name: "ING. CARLOS J. ENCARNACION GONZALEZ",
    right_title1: "1er Tt. Ingeniero en Sistema FARD.",
    right_title2: "Encargado del Departamento Administrativo de la",
    right_title3: 'Sub Dirección de Recursos Humanos del Hosp. Mil. Univ. Doc. FARD, "DRL".',
  };
  return { SIGNATURES: signatures, mockSaveReportSignatures: vi.fn() };
});

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    listRanks: vi.fn().mockResolvedValue([
      { id: "rank-1", name: "Capitán", abbreviation: "Cap.", active: false },
    ]),
    createRank: vi.fn(),
    updateRank: (...args: unknown[]) => mockUpdateRank(...args),
    deleteRank: vi.fn(),
    listDepartments: vi.fn().mockResolvedValue([]),
    createDepartment: vi.fn(),
    updateDepartment: vi.fn(),
    deleteDepartment: vi.fn(),
    getReportSignatures: vi.fn().mockResolvedValue(SIGNATURES),
    saveReportSignatures: (...args: unknown[]) => mockSaveReportSignatures(...args),
    listDeactivationReasons: vi.fn().mockResolvedValue([
      {
        id: "reason-1",
        code: "medical_leave",
        display_name: "Licencia médica",
        active: true,
        requires_detail: false,
        applies_to_sex: null,
        severity: "hard_block",
        expects_return: true,
      },
      {
        id: "reason-2",
        code: "vacaciones",
        display_name: "Vacaciones",
        active: false,
        requires_detail: false,
        applies_to_sex: null,
        severity: "hard_block",
        expects_return: false,
      },
    ]),
    createDeactivationReason: (...args: unknown[]) => mockCreateDeactivationReason(...args),
    updateDeactivationReason: (...args: unknown[]) => mockUpdateDeactivationReason(...args),
    deleteDeactivationReason: vi.fn(),
  },
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <CatalogsPage />
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("CatalogsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSaveReportSignatures.mockResolvedValue(SIGNATURES);
  });

  it("updates rank active status from the catalog tab", async () => {
    renderPage();

    expect(await screen.findByText("Capitán")).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();

    const row = screen.getByText("Capitán").closest("tr");
    expect(row).not.toBeNull();
    fireEvent.click(within(row as HTMLTableRowElement).getByTitle("Editar rango"));
    fireEvent.click(screen.getByLabelText("Inactivo"));
    fireEvent.click(screen.getByRole("button", { name: /Guardar/i }));

    await waitFor(() => {
      expect(mockUpdateRank).toHaveBeenCalledWith("rank-1", {
        name: "Capitán",
        abbreviation: "Cap.",
        active: true,
      });
    });
  });

  it("creates deactivation reasons from the catalog tab", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /Razones de desactivación/i }));
    expect(await screen.findByText("Licencia médica")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Nueva Razón/i }));
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Capacitación" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Crear$/i }));

    await waitFor(() => {
      expect(mockCreateDeactivationReason).toHaveBeenCalledWith({
        display_name: "Capacitación",
        applies_to_sex: null,
        expects_return: true,
      });
    });
  });

  it("updates deactivation reason active status from the catalog tab", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /Razones de desactivación/i }));
    expect(await screen.findByText("Vacaciones")).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();

    const row = screen.getByText("Vacaciones").closest("tr");
    expect(row).not.toBeNull();
    fireEvent.click(within(row as HTMLTableRowElement).getByTitle("Editar razón"));
    fireEvent.click(screen.getByLabelText("Inactivo"));
    fireEvent.click(screen.getByRole("button", { name: /Guardar/i }));

    await waitFor(() => {
      expect(mockUpdateDeactivationReason).toHaveBeenCalledWith("reason-2", {
        display_name: "Vacaciones",
        applies_to_sex: null,
        expects_return: false,
        active: true,
      });
    });
  });

  it("muestra si cada motivo espera fecha de regreso", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /Razones de desactivación/i }));
    expect(await screen.findByText("Licencia médica")).toBeInTheDocument();

    // La columna es la que gobierna la pantalla de "No disponible": un motivo que no espera
    // regreso (como DIRECCION) hace que no se pida fecha.
    const conRegreso = screen.getByText("Licencia médica").closest("tr") as HTMLTableRowElement;
    const sinRegreso = screen.getByText("Vacaciones").closest("tr") as HTMLTableRowElement;
    expect(within(conRegreso).getByText("Sí")).toBeInTheDocument();
    expect(within(sinRegreso).getByText("No")).toBeInTheDocument();
  });

  it("shows both signatures in the signatures tab", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /^Firmas$/ }));

    expect(
      await screen.findByDisplayValue("ING. CARLOS J. ENCARNACION GONZALEZ")
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Sargento Médico FARD.")).toBeInTheDocument();
    // Three left titles + the four right fields: the left name is never editable here.
    expect(screen.getAllByRole("textbox")).toHaveLength(7);
    // The text is split by a <strong>, so match on the paragraph's full content.
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName === "P" &&
          (element.textContent ?? "").includes("El nombre lo pone el usuario que exporta")
      )
    ).toBeInTheDocument();
  });

  it("saves the edited signature lines", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /^Firmas$/ }));
    const rightName = await screen.findByDisplayValue("ING. CARLOS J. ENCARNACION GONZALEZ");
    fireEvent.change(rightName, { target: { value: "NUEVO FIRMANTE" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar firmas/i }));

    await waitFor(() => {
      expect(mockSaveReportSignatures).toHaveBeenCalledWith(
        expect.objectContaining({
          right_name: "NUEVO FIRMANTE",
          left_title1: "Sargento Médico FARD.",
        })
      );
    });
  });
});
