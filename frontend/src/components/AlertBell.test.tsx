import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AlertBell } from "./AlertBell";
import { actionAlertsApi } from "../api/actionAlerts";

const auth = vi.hoisted(() => ({
  state: {
    currentUser: { name: "Dr. Admin", role: "admin", permissions: [] as string[] },
  },
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => auth.state,
}));

vi.mock("../api/actionAlerts", () => ({
  actionAlertsApi: {
    summary: vi.fn().mockResolvedValue({ total_open: 3, by_section: {} }),
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    resolve: vi.fn(),
    dismiss: vi.fn(),
  },
}));

vi.mock("../api/confirmations", () => ({
  confirmationsApi: { processOverdue: vi.fn() },
}));

vi.mock("./Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function renderBell() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <AlertBell />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("AlertBell", () => {
  beforeEach(() => {
    auth.state.currentUser = { name: "Dr. Admin", role: "admin", permissions: [] };
    vi.mocked(actionAlertsApi.summary).mockClear();
    vi.mocked(actionAlertsApi.list).mockClear();
  });

  it("un usuario sin manage_alerts no consulta alertas ni ve la campana", () => {
    auth.state.currentUser = { name: "Encargado", role: "encargado", permissions: [] };
    renderBell();

    expect(screen.queryByRole("button", { name: /alertas accionables/i })).not.toBeInTheDocument();
    expect(actionAlertsApi.summary).not.toHaveBeenCalled();
    expect(actionAlertsApi.list).not.toHaveBeenCalled();
  });

  it("un encargado con manage_alerts sí ve la campana y consulta el resumen", async () => {
    auth.state.currentUser = {
      name: "Encargado",
      role: "encargado",
      permissions: ["manage_alerts"],
    };
    renderBell();

    expect(
      await screen.findByRole("button", { name: /alertas accionables: 3/i })
    ).toBeInTheDocument();
    expect(actionAlertsApi.summary).toHaveBeenCalledTimes(1);
  });
});
