import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
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
    listServiceAreas: vi.fn().mockResolvedValue([
      { id: "area-e", display_name: "Emergencia", code: "emergencia", active: true },
    ]),
    listRanks: vi.fn().mockResolvedValue([
      { id: "rank-active", name: "Capitán", abbreviation: "Cap.", active: true },
      { id: "rank-inactive", name: "Mayor", abbreviation: "May.", active: false },
    ]),
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

vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    fillGaps: vi.fn().mockResolvedValue({ filled: 0, remaining: 0, message: "ok" }),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DoctorForm onClose={vi.fn()} />
      </MemoryRouter>
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

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByLabelText("Apellido"), {
      target: { value: "García" },
    });
    fireEvent.change(screen.getByLabelText(/WhatsApp/), {
      target: { value: "8095551234" },
    });
    await screen.findByText("Recursos Humanos");
    fireEvent.change(screen.getByLabelText("Departamento"), {
      target: { value: "dept-1" },
    });
    fireEvent.click(screen.getByLabelText("Lun"));
    fireEvent.click(screen.getByLabelText("Emergencia"));
    fireEvent.click(screen.getByRole("button", { name: /Guardar/i }));

    await waitFor(() => {
      expect(mockCreateDoctor).toHaveBeenCalledWith(
        expect.objectContaining({
          first_name: "Ana",
          last_name: "García",
          name: "Ana García",
          department_id: "dept-1",
        })
      );
    });
  });

  it("only shows active ranks in the rank dropdown", async () => {
    renderForm();

    await screen.findByText("Capitán");

    expect(screen.getByRole("option", { name: "Capitán" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Mayor" })).not.toBeInTheDocument();
  });
});
