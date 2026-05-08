import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { App } from "./App";

vi.mock("./api/auth", () => ({
  login: vi.fn().mockResolvedValue({
    access_token: "test-token",
    user: { id: "1", name: "Admin", email: "a@test.com", role: "admin", active: true, must_change_password: true },
  }),
  changePassword: vi.fn().mockResolvedValue({
    id: "1", name: "Admin", email: "a@test.com", role: "admin", active: true, must_change_password: false,
  }),
}));

function renderApp(initialPath = "/login") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("App", () => {
  it("muestra la pantalla de login en /login", () => {
    renderApp("/login");
    expect(screen.getByRole("heading", { name: /sistema de turnos/i })).toBeInTheDocument();
  });

  it("redirige a /login en rutas desconocidas sin sesión", () => {
    renderApp("/unknown");
    expect(screen.getByRole("heading", { name: /sistema de turnos/i })).toBeInTheDocument();
  });

  it("pide cambio de contraseña después del login", async () => {
    const user = userEvent.setup();
    renderApp("/login");
    await user.type(screen.getByLabelText(/contraseña/i), "Temp123!");
    await user.click(screen.getByRole("button", { name: /entrar/i }));
    expect(await screen.findByLabelText(/nueva contraseña/i)).toBeInTheDocument();
  });
});
