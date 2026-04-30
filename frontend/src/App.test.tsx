import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";

vi.mock("./api/auth", () => ({
  login: vi.fn().mockResolvedValue({
    access_token: "test-token",
    token_type: "bearer",
    user: { id: "1", name: "Admin", email: "admin@test.local", role: "admin", active: true, must_change_password: true },
  }),
  changePassword: vi.fn().mockResolvedValue({
    id: "1", name: "Admin", email: "admin@test.local", role: "admin", active: true, must_change_password: false,
  }),
}));

function renderApp() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders the application shell", () => {
    renderApp();
    expect(screen.getByRole("heading", { name: /sistema de turnos medicos/i })).toBeInTheDocument();
  });

  it("requires password change after login", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByLabelText(/contrasena/i), "Temporary123!");
    await user.click(screen.getByRole("button", { name: /entrar/i }));

    expect(await screen.findByLabelText(/nueva contrasena/i)).toBeInTheDocument();
  });

  it("shows catalog summary after password change", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByLabelText(/contrasena/i), "Temporary123!");
    await user.click(screen.getByRole("button", { name: /entrar/i }));
    await user.type(await screen.findByLabelText(/nueva contrasena/i), "Permanent123!");
    await user.click(screen.getByRole("button", { name: /cambiar contrasena/i }));

    expect(await screen.findByRole("heading", { name: /areas mvp/i })).toBeInTheDocument();
  });
});
