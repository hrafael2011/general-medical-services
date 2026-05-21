import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CalendarList } from "./CalendarList";
import { calendarsApi } from "../../api/calendars";

vi.mock("../../api/calendars", () => ({
  calendarsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({
      id: "cal-1",
      year: 2026,
      month: 5,
      status: "draft",
      generation_mode: "manual",
      created_by: null,
      approved_by: null,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z",
      approved_at: null,
    }),
  },
}));

function renderList() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CalendarList onSelect={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("CalendarList", () => {
  it("habilita calendarios en modo manual para que abran vacíos", async () => {
    renderList();
    const userEvent = await import("@testing-library/user-event");

    await screen.findByText("No hay calendarios registrados.");
    await userEvent.default.click(screen.getByRole("button", { name: /nuevo calendario/i }));
    await userEvent.default.click(screen.getByRole("button", { name: /habilitar calendario/i }));

    await waitFor(() => {
      expect(calendarsApi.create).toHaveBeenCalledWith(2026, 5, "manual");
    });
  });
});
