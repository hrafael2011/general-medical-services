import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReportsView } from "./ReportsView";

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

vi.mock("../../api/reports", () => ({
  reportsApi: {
    downloadDoctorHistoryExcel: vi.fn(),
    getOperationalSummary: vi.fn(),
    getNotificationsSummary: vi.fn(),
  },
}));

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ReportsView />
    </QueryClientProvider>
  );
}

describe("ReportsView", () => {
  it("muestra el título Reportes", () => {
    renderComponent();
    const heading = screen.getByRole("heading", { name: /reportes/i });
    expect(heading).toBeInTheDocument();
  });

  it("muestra el botón de descarga de historial", () => {
    renderComponent();
    const button = screen.getByRole("button", { name: /descargar historial/i });
    expect(button).toBeInTheDocument();
  });

  it("muestra los botones de resumen operacional y notificaciones", () => {
    renderComponent();
    const opButton = screen.getByRole("button", { name: /resumen operacional/i });
    const notifButton = screen.getByRole("button", { name: /resumen notificaciones/i });
    expect(opButton).toBeInTheDocument();
    expect(notifButton).toBeInTheDocument();
  });
});
