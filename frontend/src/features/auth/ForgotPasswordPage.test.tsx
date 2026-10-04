import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { authApi } from "../../api/auth";
import { ApiError } from "../../api/client";

vi.mock("../../api/auth", () => ({
  authApi: { forgotPassword: vi.fn() },
}));

const mockForgotPassword = vi.mocked(authApi.forgotPassword);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/forgot-password"]}>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    mockForgotPassword.mockReset();
  });

  it("renderiza el campo de correo y el botón de envío", () => {
    renderPage();
    expect(screen.getByLabelText(/correo electrónico/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /enviar enlace/i })).toBeInTheDocument();
  });

  it("monta sobre el panel del sistema de auth, no sobre las clases que no existen", () => {
    // Estas clases se usaban sin estar definidas en styles.css: el input quedaba
    // estirado al ancho completo de la pantalla. Que no vuelvan.
    const { container } = renderPage();
    expect(container.querySelector(".auth-panel--narrow")).not.toBeNull();
    expect(container.querySelector(".login-card")).toBeNull();
    expect(container.querySelector(".login-page")).toBeNull();
    expect(container.querySelector(".form-input")).toBeNull();
  });

  it("muestra 'Solicitud enviada' tras un envío correcto", async () => {
    mockForgotPassword.mockResolvedValue({ message: "ok" });
    const { container } = renderPage();

    await userEvent.type(screen.getByLabelText(/correo electrónico/i), "user@test.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar enlace/i }));

    expect(await screen.findByText(/solicitud enviada/i)).toBeInTheDocument();
    expect(container.querySelector(".status-icon--success")).not.toBeNull();
    expect(mockForgotPassword).toHaveBeenCalledWith("user@test.com");
  });

  it("muestra 'Demasiadas solicitudes' cuando la API responde 429", async () => {
    mockForgotPassword.mockRejectedValue(new ApiError(429, "rate limited"));
    const { container } = renderPage();

    await userEvent.type(screen.getByLabelText(/correo electrónico/i), "user@test.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar enlace/i }));

    expect(await screen.findByText(/demasiadas solicitudes/i)).toBeInTheDocument();
    expect(container.querySelector(".status-icon--warning")).not.toBeNull();
  });

  it("no revela si el correo existe ante otros errores", async () => {
    mockForgotPassword.mockRejectedValue(new ApiError(500, "boom"));
    renderPage();

    await userEvent.type(screen.getByLabelText(/correo electrónico/i), "user@test.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar enlace/i }));

    expect(await screen.findByText(/solicitud enviada/i)).toBeInTheDocument();
  });
});
