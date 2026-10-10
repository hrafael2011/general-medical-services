import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../../context/AuthContext";
import { ToastProvider } from "../../components/Toast";
import { App } from "../../App";

const ADMIN = vi.hoisted(() => ({
  id: "1", name: "Admin", email: "a@test.com", role: "admin",
  active: true, must_change_password: false, is_superadmin: true, permissions: [],
}));

vi.mock("../../api/auth", () => ({
  authApi: { me: vi.fn().mockResolvedValue(ADMIN) },
  login: vi.fn(),
  changePassword: vi.fn(),
  updateProfile: vi.fn().mockResolvedValue(ADMIN),
  PASSWORD_MIN_LENGTH: 8,
}));

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
  return { ...actual, getToken: () => "test-token", setToken: vi.fn() };
});

function renderApp() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <QueryClientProvider client={qc}>
        <ToastProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe("Ruta de perfil", () => {
  it("el avatar del menú abre Mi perfil", async () => {
    renderApp();

    const avatar = await screen.findByRole("button", { name: /ver mi perfil/i });
    await userEvent.click(avatar);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /mi perfil/i })).toBeInTheDocument();
    });
  });
});
