import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../components/Toast";
import { ApiError } from "../../api/client";
import { ProfilePage } from "./ProfilePage";

const mocks = vi.hoisted(() => ({
  setCurrentUser: vi.fn(),
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
  currentUser: {
    id: "u1",
    name: "Alexandra",
    email: "alexandra@test.com",
    role: "encargado",
    active: true,
    must_change_password: false,
    is_superadmin: false,
    permissions: [],
  },
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ currentUser: mocks.currentUser, setCurrentUser: mocks.setCurrentUser }),
}));

vi.mock("../../api/auth", async () => {
  const actual = await vi.importActual<typeof import("../../api/auth")>("../../api/auth");
  return {
    ...actual,
    updateProfile: (...args: unknown[]) => mocks.updateProfile(...args),
    changePassword: (...args: unknown[]) => mocks.changePassword(...args),
  };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ProfilePage />
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra los datos del usuario con correo y rol de solo lectura", () => {
    renderPage();

    expect(screen.getByLabelText("Nombre")).toHaveValue("Alexandra");
    expect(screen.getByLabelText("Correo")).toHaveValue("alexandra@test.com");
    expect(screen.getByLabelText("Rol")).toHaveValue("Encargado");
    expect(screen.getByLabelText("Correo")).toBeDisabled();
    expect(screen.getByLabelText("Rol")).toBeDisabled();
  });

  it("guarda el nombre y refresca el contexto del menú", async () => {
    const updated = { ...mocks.currentUser, name: "DRA. ALEXANDRA ACOSTA RAMOS" };
    mocks.updateProfile.mockResolvedValue(updated);
    renderPage();

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "DRA. ALEXANDRA ACOSTA RAMOS" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Guardar$/i }));

    await waitFor(() => {
      expect(mocks.updateProfile).toHaveBeenCalledWith("DRA. ALEXANDRA ACOSTA RAMOS");
      expect(mocks.setCurrentUser).toHaveBeenCalledWith(updated);
    });
  });

  it("muestra el mensaje exacto que devuelve el backend al rechazar la contraseña", async () => {
    mocks.changePassword.mockRejectedValue(
      new ApiError(400, {
        code: "password_no_uppercase",
        message: "La contraseña debe contener al menos una mayúscula.",
      })
    );
    renderPage();

    fireEvent.change(screen.getByLabelText("Contraseña actual"), { target: { value: "Vieja1!" } });
    fireEvent.change(screen.getByLabelText("Contraseña nueva"), { target: { value: "sinmayus1!" } });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña nueva"), {
      target: { value: "sinmayus1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /cambiar contraseña/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La contraseña debe contener al menos una mayúscula."
    );
  });

  it("no envía si las contraseñas no coinciden", async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText("Contraseña actual"), { target: { value: "Vieja1!" } });
    fireEvent.change(screen.getByLabelText("Contraseña nueva"), { target: { value: "Nueva123!" } });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña nueva"), {
      target: { value: "Otra1234!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /cambiar contraseña/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("no coinciden");
    expect(mocks.changePassword).not.toHaveBeenCalled();
  });

  it("enuncia el mínimo de 8 caracteres, no 10", () => {
    renderPage();

    expect(screen.getByText(/Mínimo 8 caracteres/)).toBeInTheDocument();
    expect(screen.queryByText(/Mínimo 10 caracteres/)).not.toBeInTheDocument();
  });
});
