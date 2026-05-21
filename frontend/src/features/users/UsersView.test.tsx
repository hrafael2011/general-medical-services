import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { UsersView } from "./UsersView";

const addToast = vi.fn();

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast }),
}));

vi.mock("../../api/admin", () => ({
  adminApi: {
    listUsers: vi.fn(),
    createEncargado: vi.fn(),
    inviteUser: vi.fn(),
    sendReset: vi.fn(),
    deleteUser: vi.fn(),
    updateUser: vi.fn(),
  },
}));

function renderUsers() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UsersView />
    </QueryClientProvider>,
  );
}

describe("UsersView", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminApi } = await import("../../api/admin");
    vi.mocked(adminApi.listUsers).mockResolvedValue([]);
  });

  it("muestra el mensaje del backend cuando el email pertenece a un usuario eliminado", async () => {
    const { adminApi } = await import("../../api/admin");
    vi.mocked(adminApi.createEncargado).mockRejectedValueOnce(
      new ApiError(409, {
        code: "email_belongs_to_deleted_user",
        message: "Este correo pertenece a un usuario eliminado. Usa otro correo o restaura el usuario eliminado.",
      }),
    );

    renderUsers();

    fireEvent.click(screen.getByRole("button", { name: /nuevo usuario/i }));
    fireEvent.change(screen.getByLabelText(/nombre/i), { target: { value: "Usuario Nuevo" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "deleted@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /^crear$/i }));

    await waitFor(() => {
      expect(addToast).toHaveBeenCalledWith(
        "error",
        "Este correo pertenece a un usuario eliminado. Usa otro correo o restaura el usuario eliminado.",
      );
    });
  });
});
