import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoctorList } from "./DoctorList";

const mockListDoctors = vi.fn().mockResolvedValue({
  items: [
    { id: "d1", name: "Dr. García", sex: "male", service_active: true, active: true, participa_misiones: true, monthly_service_target: 4, monthly_service_max: 6, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: "dept-1", phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: ["area-1", "area-2"] },
    { id: "d2", name: "Dra. Pérez", sex: "female", service_active: true, active: true, participa_misiones: false, monthly_service_target: 3, monthly_service_max: 3, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: [] },
    { id: "d3", name: "Dr. Inactivo", sex: "male", service_active: false, active: true, participa_misiones: true, monthly_service_target: 3, monthly_service_max: 3, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: [] },
  ],
  total: 3,
});

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: (...args: unknown[]) => mockListDoctors(...args),
    listRanks: vi.fn().mockResolvedValue([]),
    listServiceAreas: vi.fn().mockResolvedValue([
      { id: "area-1", code: "emergencia", display_name: "Emergencia", active: true },
      { id: "area-2", code: "pista", display_name: "Pista", active: true },
    ]),
    listDepartments: vi.fn().mockResolvedValue([
      { id: "dept-1", name: "Recursos Humanos", normalized_name: "recursos humanos", active: true },
    ]),
    listDeactivationReasons: vi.fn().mockResolvedValue([
      { id: "reason-1", code: "medical_license", display_name: "Licencia médica", active: true, requires_detail: false, applies_to_sex: null, severity: "hard_block" },
      { id: "reason-2", code: "other", display_name: "Otro", active: true, requires_detail: true, applies_to_sex: null, severity: "warn" },
    ]),
    reactivateService: vi.fn(),
    deactivateService: vi.fn(),
  },
  availabilityApi: {
    list: vi.fn().mockResolvedValue([
      { id: "a1", doctor_id: "d1", availability_type: "weekly_fixed", days_of_week: [0, 2], available_dates: null, weekday: null, week_number: null, year: null, month: null },
    ]),
  },
}));

function renderList() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DoctorList onAdd={vi.fn()} onEdit={vi.fn()} />
    </QueryClientProvider>
  );
}

describe("DoctorList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListDoctors.mockResolvedValue({
      items: [
        { id: "d1", name: "Dr. García", sex: "male", service_active: true, active: true, participa_misiones: true, monthly_service_target: 4, monthly_service_max: 6, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: "dept-1", phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: ["area-1", "area-2"] },
        { id: "d2", name: "Dra. Pérez", sex: "female", service_active: true, active: true, participa_misiones: false, monthly_service_target: 3, monthly_service_max: 3, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: [] },
        { id: "d3", name: "Dr. Inactivo", sex: "male", service_active: false, active: true, participa_misiones: true, monthly_service_target: 3, monthly_service_max: 3, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: [] },
      ],
      total: 3,
    });
  });

  it("muestra el nombre del médico", async () => {
    renderList();
    expect(await screen.findByText("Dr. García")).toBeInTheDocument();
  });

  it("muestra el count de áreas", async () => {
    renderList();
    expect(await screen.findByText("2 área(s)")).toBeInTheDocument();
  });

  it("el tooltip contiene los nombres de las áreas", async () => {
    renderList();
    await screen.findByText("2 área(s)");
    expect(screen.getByText("Emergencia, Pista")).toBeInTheDocument();
  });

  it("usa columnas ejecutivas en el listado", async () => {
    renderList();
    expect(await screen.findByText("Status servicio")).toBeInTheDocument();
    expect(screen.getAllByText("Activo").length).toBeGreaterThan(0);
    expect(screen.getByText("Departamento")).toBeInTheDocument();
    expect(screen.queryByText("Sexo")).not.toBeInTheDocument();
    expect(screen.queryByText("Meta/mes")).not.toBeInTheDocument();
  });

  it("muestra el departamento del médico en la tabla", async () => {
    renderList();
    expect(await screen.findByText("Recursos Humanos")).toBeInTheDocument();
  });

  it("filtra médicos por nombre o apellido", async () => {
    renderList();
    fireEvent.change(await screen.findByLabelText("Buscar médico por nombre o apellido"), {
      target: { value: "perez" },
    });

    expect(screen.getByText("Dra. Pérez")).toBeInTheDocument();
    expect(screen.queryByText("Dr. García")).not.toBeInTheDocument();
  });

  it("muestra No en misiones cuando el médico está inactivo para servicio", async () => {
    renderList();
    const row = (await screen.findByText("Dr. Inactivo")).closest("tr");

    expect(row).not.toBeNull();
    expect(row).toHaveTextContent("Inactivo");
    expect(row).toHaveTextContent("No");
  });

  it("abre el perfil del médico desde la fila", async () => {
    renderList();
    fireEvent.click(await screen.findByText("Dr. García"));
    expect(await screen.findByText("Activo en sistema")).toBeInTheDocument();
    expect(screen.getAllByText("Activo para servicio").length).toBeGreaterThan(0);
    expect(screen.getByText("Editar médico")).toBeInTheDocument();
    expect(screen.getByText("Razón para desactivar servicio")).toBeInTheDocument();
  });

  it("solicita solo activos para servicio al activar el filtro", async () => {
    renderList();
    fireEvent.click(await screen.findByLabelText("Solo activos para servicio"));

    expect(mockListDoctors).toHaveBeenCalledWith(false);
    expect(mockListDoctors).toHaveBeenCalledWith(true);
  });
});
