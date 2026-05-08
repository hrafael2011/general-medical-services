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

const NOW = new Date();
const YEAR = NOW.getFullYear();
const MONTH = NOW.getMonth() + 1;

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: vi.fn().mockResolvedValue({ items: [{ id: "d1", service_active: true }, { id: "d2", service_active: true }], total: 2 }),
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
    const matches = await screen.findAllByText(/aprobado/i);
    expect(matches.length).toBeGreaterThan(0);
  });
});
