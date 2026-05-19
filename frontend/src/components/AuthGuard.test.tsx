import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthGuard } from "./AuthGuard";

const mockAuth = vi.hoisted(() => ({
  currentUser: null as null | { id: string; name: string },
  isAuthLoading: false,
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => mockAuth,
}));

function renderGuard() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route element={<AuthGuard />}>
          <Route path="/dashboard" element={<p>Dashboard privado</p>} />
        </Route>
        <Route path="/login" element={<p>Pantalla login</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AuthGuard", () => {
  it("muestra carga y no redirige mientras restaura sesión", () => {
    mockAuth.currentUser = null;
    mockAuth.isAuthLoading = true;

    renderGuard();

    expect(screen.getByText("Restaurando sesión…")).toBeInTheDocument();
    expect(screen.queryByText("Pantalla login")).not.toBeInTheDocument();
  });

  it("redirige al login cuando no hay sesión restaurable", () => {
    mockAuth.currentUser = null;
    mockAuth.isAuthLoading = false;

    renderGuard();

    expect(screen.getByText("Pantalla login")).toBeInTheDocument();
  });
});
