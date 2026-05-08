import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportView } from "./ImportView";

vi.mock("../../api/import_staging", () => ({
  importApi: {
    uploadFile: vi.fn(),
    listFiles: vi.fn(),
    listStaged: vi.fn(),
    reviewRecord: vi.fn(),
    applyApproved: vi.fn(),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({
    addToast: vi.fn(),
  }),
}));

function renderImport() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ImportView />
    </QueryClientProvider>
  );
}

describe("ImportView", () => {
  it("muestra el panel de subida de archivos", async () => {
    const { importApi } = await import("../../api/import_staging");
    vi.mocked(importApi.listFiles).mockResolvedValueOnce({
      items: [],
      total: 0,
    });

    renderImport();

    const heading = await screen.findByRole("heading", { name: /subir archivo/i });
    expect(heading).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay archivos importados", async () => {
    const { importApi } = await import("../../api/import_staging");
    vi.mocked(importApi.listFiles).mockResolvedValueOnce({
      items: [],
      total: 0,
    });

    renderImport();

    const emptyText = await screen.findByText(/no hay archivos importados/i);
    expect(emptyText).toBeInTheDocument();
  });

  it("muestra el nombre del archivo en la tabla", async () => {
    const { importApi } = await import("../../api/import_staging");
    vi.mocked(importApi.listFiles).mockResolvedValueOnce({
      items: [
        {
          id: "f1",
          file_name: "turnos_mayo.xlsx",
          file_type: "xlsx",
          status: "ready",
          record_count: 10,
          detected_period_year: 2026,
          detected_period_month: 5,
          imported_at: "2026-05-01T00:00:00",
        },
      ],
      total: 1,
    });

    renderImport();

    const fileName = await screen.findByText("turnos_mayo.xlsx");
    expect(fileName).toBeInTheDocument();
  });
});
