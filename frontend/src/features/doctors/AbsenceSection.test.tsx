import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AbsenceSection } from "./AbsenceSection";
import type { DeactivationReasonRead, DoctorRestrictionRead } from "../../api/doctors";

const mockListRestrictions = vi.fn();
const mockAddRestriction = vi.fn().mockResolvedValue({});
const mockUpdateRestriction = vi.fn().mockResolvedValue({});
const mockLiftRestriction = vi.fn().mockResolvedValue({});
const mockAddToast = vi.fn();

vi.mock("../../api/doctors", () => ({
  availabilityApi: {
    listRestrictions: (...args: unknown[]) => mockListRestrictions(...args),
    addRestriction: (...args: unknown[]) => mockAddRestriction(...args),
    updateRestriction: (...args: unknown[]) => mockUpdateRestriction(...args),
    liftRestriction: (...args: unknown[]) => mockLiftRestriction(...args),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: mockAddToast }),
}));

// Fechas relativas a hoy, para que las ausencias sean "vigentes" o "programadas" según el
// caso y no dependan del día en que se corran los tests.
function iso(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

const REASONS: DeactivationReasonRead[] = [
  {
    id: "r-licencia",
    code: "licencias_medicas",
    display_name: "LICENCIAS MEDICAS",
    active: true,
    requires_detail: false,
    applies_to_sex: null,
    severity: "hard_block",
    expects_return: true,
  },
  {
    id: "r-direccion",
    code: "direccion",
    display_name: "DIRECCION",
    active: true,
    requires_detail: false,
    applies_to_sex: null,
    severity: "hard_block",
    expects_return: false,
  },
];

function restriction(overrides: Partial<DoctorRestrictionRead>): DoctorRestrictionRead {
  return {
    id: "res-1",
    doctor_id: "doc-1",
    reason_id: "r-licencia",
    restriction_type: "license",
    severity: "hard_block",
    description: null,
    starts_at: iso(-2),
    ends_at: iso(5),
    source: "manual",
    review_status: "approved",
    lifted_at: null,
    lifted_by: null,
    ...overrides,
  };
}

function renderSection(props: Partial<Parameters<typeof AbsenceSection>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AbsenceSection
        doctorId="doc-1"
        reasons={REASONS}
        serviceActive
        inactiveReasonName={null}
        inactiveDetail={null}
        {...props}
      />
    </QueryClientProvider>
  );
}

describe("AbsenceSection", () => {
  beforeEach(() => {
    mockListRestrictions.mockReset();
    mockAddRestriction.mockClear();
    mockUpdateRestriction.mockClear();
    mockLiftRestriction.mockClear();
    mockAddToast.mockClear();
  });

  it("muestra la ausencia con fechas y la fecha de reintegro", async () => {
    mockListRestrictions.mockResolvedValue([restriction({})]);

    renderSection();

    expect(await screen.findByText("LICENCIAS MEDICAS")).toBeInTheDocument();
    const esperado = iso(5).split("-").reverse().join("/");
    expect(screen.getByText(new RegExp(`se reintegra el ${esperado}`))).toBeInTheDocument();
    expect(screen.getByText("Vigente")).toBeInTheDocument();
  });

  it("muestra el flag sin fecha como otra forma de no estar disponible", async () => {
    mockListRestrictions.mockResolvedValue([]);

    renderSection({ serviceActive: false, inactiveReasonName: "VACACIONES" });

    expect(await screen.findByText("VACACIONES")).toBeInTheDocument();
    expect(screen.getByText(/sin fecha de regreso/i)).toBeInTheDocument();
  });

  it("distingue lo programado de lo vigente", async () => {
    mockListRestrictions.mockResolvedValue([
      restriction({ id: "res-futura", starts_at: iso(3), ends_at: iso(9) }),
    ]);

    renderSection();

    expect(await screen.findByText("Programada")).toBeInTheDocument();
  });

  it("marca Indefinido solo cuando el motivo no espera regreso", async () => {
    mockListRestrictions.mockResolvedValue([]);

    renderSection();

    fireEvent.click(await screen.findByRole("button", { name: /registrar ausencia/i }));
    const indefinite = screen.getByLabelText(/indefinido/i);
    const endDate = screen.getByLabelText(/hasta/i);
    expect(indefinite).not.toBeChecked();
    expect(endDate).not.toBeDisabled();

    // DIRECCION es un puesto, no una ausencia: la pantalla propone Indefinido.
    fireEvent.change(screen.getByLabelText(/motivo/i), { target: { value: "r-direccion" } });

    expect(indefinite).toBeChecked();
    expect(endDate).toBeDisabled();
  });

  it("no deja guardar una fecha de regreso anterior al inicio", async () => {
    mockListRestrictions.mockResolvedValue([]);

    renderSection();

    fireEvent.click(await screen.findByRole("button", { name: /registrar ausencia/i }));
    fireEvent.change(screen.getByLabelText(/motivo/i), { target: { value: "r-licencia" } });
    fireEvent.change(screen.getByLabelText(/^desde/i), { target: { value: iso(5) } });
    fireEvent.change(screen.getByLabelText(/hasta/i), { target: { value: iso(1) } });
    fireEvent.click(screen.getByRole("button", { name: /^guardar$/i }));

    expect(await screen.findByText(/no puede ser anterior/i)).toBeInTheDocument();
    expect(mockAddRestriction).not.toHaveBeenCalled();
  });

  it("guarda una ausencia indefinida con ends_at nulo", async () => {
    mockListRestrictions.mockResolvedValue([]);

    renderSection();

    fireEvent.click(await screen.findByRole("button", { name: /registrar ausencia/i }));
    fireEvent.change(screen.getByLabelText(/motivo/i), { target: { value: "r-direccion" } });
    fireEvent.change(screen.getByLabelText(/^desde/i), { target: { value: iso(1) } });
    fireEvent.click(screen.getByRole("button", { name: /^guardar$/i }));

    await waitFor(() =>
      expect(mockAddRestriction).toHaveBeenCalledWith("doc-1", {
        restriction_type: "license",
        severity: "hard_block",
        starts_at: iso(1),
        ends_at: null,
        reason_id: "r-direccion",
      })
    );
  });

  it("permite levantar una ausencia", async () => {
    mockListRestrictions.mockResolvedValue([restriction({})]);

    renderSection();

    const row = (await screen.findByText("LICENCIAS MEDICAS")).closest(".absence-row")!;
    fireEvent.click(within(row as HTMLElement).getByTitle(/levantar ausencia/i));

    await waitFor(() => expect(mockLiftRestriction).toHaveBeenCalledWith("res-1"));
  });

  it("editar la fecha usa la misma ausencia en vez de crear otra", async () => {
    mockListRestrictions.mockResolvedValue([restriction({})]);

    renderSection();

    const row = (await screen.findByText("LICENCIAS MEDICAS")).closest(".absence-row")!;
    fireEvent.click(within(row as HTMLElement).getByTitle(/editar ausencia/i));
    fireEvent.change(screen.getByLabelText(/hasta/i), { target: { value: iso(12) } });
    fireEvent.click(screen.getByRole("button", { name: /^guardar$/i }));

    await waitFor(() =>
      expect(mockUpdateRestriction).toHaveBeenCalledWith("res-1", {
        severity: "hard_block",
        starts_at: iso(-2),
        ends_at: iso(12),
        reason_id: "r-licencia",
      })
    );
    expect(mockAddRestriction).not.toHaveBeenCalled();
  });
});
