import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { DashboardView } from "./DashboardView";

vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    list: vi.fn().mockResolvedValue([
      { id: "cal-1", year: new Date().getFullYear(), month: new Date().getMonth() + 1, status: "approved" },
    ]),
  },
}));

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: vi.fn().mockResolvedValue({ items: [{ id: "d1", service_active: true }, { id: "d2", service_active: true }], total: 2 }),
  },
}));

vi.mock("../../api/missions", () => ({
  missionsApi: {
    getReplacementAlertSummary: vi.fn().mockResolvedValue({ mission_count: 1, participant_count: 1 }),
  },
}));

function renderDashboard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <DashboardView />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("DashboardView", () => {
  it("muestra el KPI de médicos activos", async () => {
    renderDashboard();
    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.getByText(/médicos activos/i)).toBeInTheDocument();
  });

  it("muestra alerta de calendario aprobado", async () => {
    renderDashboard();
    expect(await screen.findByText(/calendario .* aprobado/i)).toBeInTheDocument();
    expect(screen.getByText("Aprobado")).toBeInTheDocument();
  });

  it("muestra alerta operativa de reemplazos pendientes", async () => {
    renderDashboard();
    expect(await screen.findByText(/misión futura requiere reemplazo/i)).toBeInTheDocument();
    expect(screen.getByText(/participante\(s\) deben ser reemplazados/i)).toBeInTheDocument();
  });
});
