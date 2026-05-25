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
});
const mockUpdateRank = vi.fn().mockResolvedValue({});
const mockUpdateDeactivationReason = vi.fn().mockResolvedValue({});

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
    listDeactivationReasons: vi.fn().mockResolvedValue([
      {
        id: "reason-1",
        code: "medical_leave",
        display_name: "Licencia médica",
        active: true,
        requires_detail: false,
        applies_to_sex: null,
        severity: "hard_block",
      },
      {
        id: "reason-2",
        code: "vacaciones",
        display_name: "Vacaciones",
        active: false,
        requires_detail: false,
        applies_to_sex: null,
        severity: "hard_block",
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
        active: true,
      });
    });
  });
});
