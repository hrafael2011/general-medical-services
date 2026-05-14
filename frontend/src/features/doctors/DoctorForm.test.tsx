import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoctorForm } from "./DoctorForm";

const mockSetWeekly = vi.fn().mockResolvedValue({});
const mockSetMonthly = vi.fn().mockResolvedValue({});
const mockSetRecurring = vi.fn().mockResolvedValue({});
const mockCreateDoctor = vi.fn().mockResolvedValue({ id: "d-new", name: "TEST" });
const mockUpdateDoctor = vi.fn().mockResolvedValue({ id: "d-edit", name: "TEST" });

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    create: (...args: unknown[]) => mockCreateDoctor(...args),
    update: (...args: unknown[]) => mockUpdateDoctor(...args),
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listServiceAreas: vi.fn().mockResolvedValue([]),
    listRanks: vi.fn().mockResolvedValue([]),
    listDepartments: vi.fn().mockResolvedValue([
      { id: "dept-1", name: "Recursos Humanos", normalized_name: "recursos humanos", active: true },
    ]),
  },
  availabilityApi: {
    setWeekly: (...args: unknown[]) => mockSetWeekly(...args),
    setMonthly: (...args: unknown[]) => mockSetMonthly(...args),
    setRecurring: (...args: unknown[]) => mockSetRecurring(...args),
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
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows weekly day chips by default", () => {
    renderForm();
    expect(screen.getByText(/Mismos días/)).toBeInTheDocument();
    expect(screen.getByText("Lun")).toBeInTheDocument();
    expect(screen.getByText("Dom")).toBeInTheDocument();
  });

  it("shows monthly grid when monthly toggle selected", () => {
    renderForm();
    fireEvent.click(screen.getByText(/Avisa sus días/));
    expect(screen.getByText("15")).toBeInTheDocument();
  });

  it("shows recurring selectors when recurring toggle selected", () => {
    renderForm();
    fireEvent.click(screen.getByText(/Día fijo/));
    expect(screen.getByText("Última")).toBeInTheDocument();
    expect(screen.getByText("Vie")).toBeInTheDocument();
  });

  it("toggles day checkbox selection on click", () => {
    renderForm();
    const lunCheckbox = screen.getByLabelText("Lun");
    expect(lunCheckbox).not.toBeChecked();
    fireEvent.click(lunCheckbox);
    expect(lunCheckbox).toBeChecked();
    fireEvent.click(lunCheckbox);
    expect(lunCheckbox).not.toBeChecked();
  });

  it("sends selected department when creating a doctor", async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText("Nombre completo"), {
      target: { value: "Dra. Prueba" },
    });
    await screen.findByText("Recursos Humanos");
    fireEvent.change(screen.getByLabelText("Departamento"), {
      target: { value: "dept-1" },
    });
    fireEvent.click(screen.getByLabelText("Lun"));
    fireEvent.click(screen.getByRole("button", { name: /Guardar/i }));

    await waitFor(() => {
      expect(mockCreateDoctor).toHaveBeenCalledWith(
        expect.objectContaining({ department_id: "dept-1" })
      );
    });
  });
});
