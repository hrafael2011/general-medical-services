import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoctorForm } from "./DoctorForm";

const mockSetWeekly = vi.fn().mockResolvedValue({});
const mockSetMonthly = vi.fn().mockResolvedValue({});
const mockSetRecurring = vi.fn().mockResolvedValue({});

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    create: vi.fn().mockResolvedValue({ id: "d-new", name: "TEST" }),
    update: vi.fn().mockResolvedValue({ id: "d-edit", name: "TEST" }),
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listServiceAreas: vi.fn().mockResolvedValue([]),
    listRanks: vi.fn().mockResolvedValue([]),
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
  it("shows weekly day chips by default", () => {
    renderForm();
    expect(screen.getByText("Trabaja los mismos días todas las semanas")).toBeInTheDocument();
    expect(screen.getByText("Lun")).toBeInTheDocument();
    expect(screen.getByText("Dom")).toBeInTheDocument();
  });

  it("shows monthly grid when monthly radio selected", () => {
    renderForm();
    fireEvent.click(screen.getByLabelText("Avisa sus días cada mes"));
    expect(screen.getByText("15")).toBeInTheDocument();
  });

  it("shows recurring selectors when recurring radio selected", () => {
    renderForm();
    fireEvent.click(screen.getByLabelText("Tiene un día fijo al mes"));
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
});
