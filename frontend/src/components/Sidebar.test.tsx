import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "./Sidebar";

// Mutable so a test can switch roles; `vi.mock` is hoisted, hence vi.hoisted.
const auth = vi.hoisted(() => ({
  state: { currentUser: { name: "Dr. Admin", role: "admin" }, logout: vi.fn() },
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => auth.state,
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

function renderSidebarWithProfileRoute() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <QueryClientProvider client={qc}>
        <Routes>
          <Route path="/dashboard" element={<Sidebar />} />
          <Route path="/profile" element={<div>PANTALLA PERFIL</div>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    auth.state.currentUser = { name: "Dr. Admin", role: "admin" };
  });
  it("muestra el título del sistema", () => {
    renderSidebar();
    // El título visual es el logo del sidebar (imagen con alt accesible)
    expect(screen.getByRole("img", { name: /sistema de turnos médicos/i })).toBeInTheDocument();
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

  it("abre Mi perfil al pulsar el bloque del usuario", async () => {
    renderSidebarWithProfileRoute();

    fireEvent.click(screen.getByRole("button", { name: /ver mi perfil/i }));

    await waitFor(() => {
      expect(screen.getByText("PANTALLA PERFIL")).toBeInTheDocument();
    });
  });

  it("oculta Auditoría a los encargados", () => {
    auth.state.currentUser = { name: "Encargado", role: "encargado" };
    renderSidebar();

    expect(screen.queryByRole("link", { name: /auditoría/i })).not.toBeInTheDocument();
  });

  it("muestra Auditoría al administrador", () => {
    renderSidebar();

    expect(screen.getByRole("link", { name: /auditoría/i })).toBeInTheDocument();
  });
});
