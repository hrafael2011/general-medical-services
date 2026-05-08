import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DoctorList } from "./DoctorList";

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: vi.fn().mockResolvedValue({
      items: [{ id: "d1", name: "Dr. García", sex: "male", service_active: true, active: true, participa_misiones: true, monthly_service_target: 4, monthly_service_max: 6, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null, allowed_area_ids: ["area-1", "area-2"] }],
      total: 1,
    }),
    listRanks: vi.fn().mockResolvedValue([]),
    listServiceAreas: vi.fn().mockResolvedValue([
      { id: "area-1", code: "emergencia", display_name: "Emergencia", active: true },
      { id: "area-2", code: "pista", display_name: "Pista", active: true },
    ]),
    reactivateService: vi.fn(),
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
});
