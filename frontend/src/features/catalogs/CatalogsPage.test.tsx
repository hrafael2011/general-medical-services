import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../components/Toast";
import { CatalogsPage } from "./CatalogsPage";

const mockCreateDeactivationReason = vi.fn().mockResolvedValue({
  id: "reason-new",
  code: "training_leave",
  display_name: "Capacitación",
  active: true,
  requires_detail: true,
  applies_to_sex: null,
  severity: "warn",
});

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    listRanks: vi.fn().mockResolvedValue([]),
    createRank: vi.fn(),
    updateRank: vi.fn(),
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
    ]),
    createDeactivationReason: (...args: unknown[]) => mockCreateDeactivationReason(...args),
    updateDeactivationReason: vi.fn(),
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

  it("creates deactivation reasons from the catalog tab", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /Razones de desactivación/i }));
    expect(await screen.findByText("Licencia médica")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Nueva Razón/i }));
    fireEvent.change(screen.getByLabelText("Código"), {
      target: { value: "training_leave" },
    });
    fireEvent.change(screen.getByLabelText("Nombre visible"), {
      target: { value: "Capacitación" },
    });
    fireEvent.click(screen.getByLabelText("Requiere detalle"));
    fireEvent.change(screen.getByLabelText("Severidad"), {
      target: { value: "warn" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Crear$/i }));

    await waitFor(() => {
      expect(mockCreateDeactivationReason).toHaveBeenCalledWith({
        code: "training_leave",
        display_name: "Capacitación",
        requires_detail: true,
        applies_to_sex: null,
        severity: "warn",
      });
    });
  });
});
