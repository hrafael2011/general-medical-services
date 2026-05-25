import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ToastProvider } from "../../components/Toast";
import { TrashPage } from "./TrashPage";

const mockListTrash = vi.fn((type: string) => Promise.resolve(
  type === "deactivation_reasons"
    ? [{
        id: "reason-1",
        name: "Capacitación",
        deleted_at: "2026-05-23T00:00:00Z",
        code: "capacitacion",
      }]
    : []
));
const mockHardDelete = vi.fn().mockResolvedValue(undefined);

vi.mock("../../api/trash", () => ({
  trashApi: {
    list: (type: string) => mockListTrash(type),
    counts: vi.fn().mockResolvedValue({
      doctors: 0,
      users: 0,
      ranks: 0,
      departments: 0,
      deactivation_reasons: 1,
    }),
    restore: vi.fn().mockResolvedValue(undefined),
    hardDelete: (...args: unknown[]) => mockHardDelete(...args),
  },
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TrashPage />
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("TrashPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows and permanently deletes deactivation reasons from trash", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Razones de desactivación \(1\)/i }));

    expect(await screen.findByText("Capacitación")).toBeInTheDocument();
    expect(screen.getByText("capacitacion")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Eliminar def\./i }));
    fireEvent.click(screen.getByRole("button", { name: /Sí, eliminar/i }));

    await waitFor(() => {
      expect(mockHardDelete).toHaveBeenCalledWith("deactivation_reasons", "reason-1");
    });
  });
});
