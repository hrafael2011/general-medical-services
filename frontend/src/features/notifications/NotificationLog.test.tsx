import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationLog } from "./NotificationLog";

vi.mock("../../api/notifications", () => ({
  notificationsApi: {
    list: vi.fn(),
    process: vi.fn(),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({
    addToast: vi.fn(),
  }),
}));

function renderNotifications() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <NotificationLog />
    </QueryClientProvider>
  );
}

describe("NotificationLog", () => {
  it("muestra el título Notificaciones", async () => {
    const { notificationsApi } = await import("../../api/notifications");
    vi.mocked(notificationsApi.list).mockResolvedValueOnce({
      items: [],
      total: 0,
    });

    renderNotifications();

    const heading = await screen.findByRole("heading", {
      name: /notificaciones/i,
    });
    expect(heading).toBeInTheDocument();
  });

  it("muestra el botón de procesar cola", async () => {
    const { notificationsApi } = await import("../../api/notifications");
    vi.mocked(notificationsApi.list).mockResolvedValueOnce({
      items: [],
      total: 0,
    });

    renderNotifications();

    const button = await screen.findByRole("button", {
      name: /procesar cola/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("muestra las notificaciones en la tabla", async () => {
    const { notificationsApi } = await import("../../api/notifications");
    vi.mocked(notificationsApi.list).mockResolvedValueOnce({
      items: [
        {
          id: "n1",
          notification_type: "initial_assignment",
          recipient_doctor_id: "d1",
          recipient_phone: null,
          assignment_id: null,
          mission_id: null,
          idempotency_key: "key1",
          scheduled_for: null,
          sent_at: null,
          status: "sent",
          provider: null,
          provider_message_id: null,
          error_code: null,
          error_message: null,
          retry_count: 0,
          payload: null,
          created_at: "2026-05-01T00:00:00",
          updated_at: "2026-05-01T00:00:00",
        },
      ],
      total: 1,
    });

    renderNotifications();

    const typeLabel = await screen.findByText("Asignación inicial");
    expect(typeLabel).toBeInTheDocument();

    const statusLabel = screen.getByText("Enviado");
    expect(statusLabel).toBeInTheDocument();
  });
});
