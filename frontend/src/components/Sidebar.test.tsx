import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ currentUser: { name: "Dr. Admin" }, logout: vi.fn() }),
}));

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  it("muestra el título del sistema", () => {
    renderSidebar();
    expect(screen.getByText(/sistema de turnos/i)).toBeInTheDocument();
  });

  it("muestra los tres grupos de navegación", () => {
    renderSidebar();
    expect(screen.getByText("OPERACIONES")).toBeInTheDocument();
    expect(screen.getByText("DATOS")).toBeInTheDocument();
    expect(screen.getByText("SISTEMA")).toBeInTheDocument();
  });

  it("muestra el nombre del usuario actual", () => {
    renderSidebar();
    expect(screen.getByText("Dr. Admin")).toBeInTheDocument();
  });

  it("muestra los links de navegación principales", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: /calendarios/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /médicos/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /misiones/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /reportes/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /importar/i })).toBeInTheDocument();
  });
});
