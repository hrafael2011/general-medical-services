import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "./Sidebar";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ currentUser: { name: "Dr. Admin", role: "admin" }, logout: vi.fn() }),
}));

vi.mock("../api/actionAlerts", () => ({
  actionAlertsApi: {
    summary: vi.fn().mockResolvedValue({ total_open: 1, by_section: { missions: 1 } }),
  },
}));

vi.mock("../api/featureFlags", () => ({
  fetchFeatureFlags: vi.fn().mockResolvedValue({ notifications: true, telegram: true }),
}));

function renderSidebar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <Sidebar />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  it("muestra el título del sistema", () => {
    renderSidebar();
    expect(screen.getByText(/sistema de turnos/i)).toBeInTheDocument();
  });

  it("muestra los tres grupos de navegación", async () => {
    renderSidebar();
    expect(screen.getByText("OPERACIONES")).toBeInTheDocument();
    expect(screen.getByText("ADMINISTRACIÓN")).toBeInTheDocument();
    expect(screen.getByText("SEGURIDAD")).toBeInTheDocument();
    expect(await screen.findByText("NOTIFICACIONES")).toBeInTheDocument();
  });

  it("muestra el nombre del usuario actual", () => {
    renderSidebar();
    expect(screen.getByText("Dr. Admin")).toBeInTheDocument();
  });

  it("muestra los links de navegación principales", async () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: /calendarios/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /médicos/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /misiones/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /reportes/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /auditoría/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /usuarios/i })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /notificaciones/i })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /telegram/i })).toBeInTheDocument();
  });

  it("muestra badge de misiones con alertas pendientes", async () => {
    renderSidebar();
    expect(await screen.findByLabelText(/alertas en misiones/i)).toHaveTextContent("1");
  });
});
