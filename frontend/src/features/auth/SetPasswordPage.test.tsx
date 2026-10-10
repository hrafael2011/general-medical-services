import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { SetPasswordPage } from "./SetPasswordPage";
import { ToastProvider } from "../../components/Toast";
import { authApi } from "../../api/auth";

vi.mock("../../api/auth", () => ({
  authApi: { validateSetPasswordToken: vi.fn(), setPassword: vi.fn() },
  PASSWORD_MIN_LENGTH: 8,
}));

const mockValidate = vi.mocked(authApi.validateSetPasswordToken);
const mockSetPassword = vi.mocked(authApi.setPassword);

function renderPage(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ToastProvider>
        <SetPasswordPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

const validToken = {
  valid: true,
  email: "user@test.com",
  name: "Dra. Test",
};

describe("SetPasswordPage", () => {
  beforeEach(() => {
    mockValidate.mockReset();
    mockSetPassword.mockReset();
  });

  it("muestra el enlace inválido cuando no hay token en la URL", async () => {
    const { container } = renderPage("/set-password");
    expect(await screen.findByText(/enlace inválido o expirado/i)).toBeInTheDocument();
    expect(container.querySelector(".status-icon--danger")).not.toBeNull();
    expect(mockValidate).not.toHaveBeenCalled();
  });

  it("muestra el enlace inválido cuando la API rechaza el token", async () => {
    mockValidate.mockResolvedValue({ valid: false });
    renderPage("/set-password?token=basura");
    expect(await screen.findByText(/enlace inválido o expirado/i)).toBeInTheDocument();
  });

  it("monta sobre el panel del sistema de auth, no sobre las clases que no existen", async () => {
    mockValidate.mockResolvedValue(validToken);
    const { container } = renderPage("/set-password?token=abc");

    await screen.findByLabelText(/nueva contraseña/i);
    expect(container.querySelector(".auth-panel--narrow")).not.toBeNull();
    expect(container.querySelector(".login-card")).toBeNull();
    expect(container.querySelector(".form-group")).toBeNull();
    expect(container.querySelector(".form-hint")).toBeNull();
  });

  it("muestra el formulario con el correo precargado y deshabilitado", async () => {
    mockValidate.mockResolvedValue(validToken);
    renderPage("/set-password?token=abc");

    const emailField = await screen.findByLabelText(/correo electrónico/i);
    expect(emailField).toHaveValue("user@test.com");
    expect(emailField).toBeDisabled();
    expect(screen.getByLabelText(/nueva contraseña/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirmar contraseña/i)).toBeInTheDocument();
  });

  it("no envía si las contraseñas no coinciden", async () => {
    mockValidate.mockResolvedValue(validToken);
    renderPage("/set-password?token=abc");

    await userEvent.type(await screen.findByLabelText(/nueva contraseña/i), "Password123!");
    await userEvent.type(screen.getByLabelText(/confirmar contraseña/i), "OtraCosa123!");
    await userEvent.click(screen.getByRole("button", { name: /crear contraseña y acceder/i }));

    expect(await screen.findByText(/las contraseñas no coinciden/i)).toBeInTheDocument();
    expect(mockSetPassword).not.toHaveBeenCalled();
  });

  it("envía el token y la contraseña cuando coinciden", async () => {
    mockValidate.mockResolvedValue(validToken);
    mockSetPassword.mockResolvedValue({ message: "ok" });
    renderPage("/set-password?token=abc");

    await userEvent.type(await screen.findByLabelText(/nueva contraseña/i), "Password123!");
    await userEvent.type(screen.getByLabelText(/confirmar contraseña/i), "Password123!");
    await userEvent.click(screen.getByRole("button", { name: /crear contraseña y acceder/i }));

    expect(await screen.findByText(/contraseña creada/i)).toBeInTheDocument();
    expect(mockSetPassword).toHaveBeenCalledWith("abc", "Password123!");
  });
});
