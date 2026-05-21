import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TelegramLinks } from "./TelegramLinks";

vi.mock("../../api/telegram", () => ({
  telegramApi: {
    listLinks: vi.fn(),
    listLinkTokens: vi.fn(),
    createLink: vi.fn(),
    deleteLink: vi.fn(),
    generateLinkToken: vi.fn(),
  },
}));

vi.mock("../../api/admin", () => ({
  adminApi: {
    listUsers: vi.fn(),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TelegramLinks />
    </QueryClientProvider>
  );
}

describe("TelegramLinks", () => {
  it("muestra el título de la sección", async () => {
    const { telegramApi } = await import("../../api/telegram");
    const { adminApi } = await import("../../api/admin");

    vi.mocked(telegramApi.listLinks).mockResolvedValue([]);
    vi.mocked(telegramApi.listLinkTokens).mockResolvedValue([]);
    vi.mocked(adminApi.listUsers).mockResolvedValue([]);

    renderComponent();

    const heading = await screen.findByRole("heading", { name: /telegram/i });
    expect(heading).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay vínculos", async () => {
    const { telegramApi } = await import("../../api/telegram");
    const { adminApi } = await import("../../api/admin");

    vi.mocked(telegramApi.listLinks).mockResolvedValue([]);
    vi.mocked(telegramApi.listLinkTokens).mockResolvedValue([]);
    vi.mocked(adminApi.listUsers).mockResolvedValue([]);

    renderComponent();

    const emptyText = await screen.findByText(/no hay vinculos/i);
    expect(emptyText).toBeInTheDocument();
  });

  it("muestra la tabla cuando hay vínculos", async () => {
    const { telegramApi } = await import("../../api/telegram");
    const { adminApi } = await import("../../api/admin");

    vi.mocked(telegramApi.listLinks).mockResolvedValue([
      {
        id: "l1",
        telegram_user_id: "123456",
        telegram_username: "@test",
        user_id: "u1",
        linked_at: "2026-01-01T00:00:00",
        linked_by: null,
        last_used_at: null,
        active: true,
      },
    ]);
    vi.mocked(telegramApi.listLinkTokens).mockResolvedValue([]);
    vi.mocked(adminApi.listUsers).mockResolvedValue([]);

    renderComponent();

    const telegramUserId = await screen.findByText("123456");
    expect(telegramUserId).toBeInTheDocument();
  });
});
