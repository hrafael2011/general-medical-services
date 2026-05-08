import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuditLog } from "./AuditLog";
import { AuditListResponse } from "../../api/audit";

vi.mock("../../api/audit", () => ({
  auditApi: {
    list: vi.fn(),
  },
}));

function renderAudit() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuditLog />
    </QueryClientProvider>
  );
}

describe("AuditLog", () => {
  it("muestra el título Auditoría", async () => {
    const { auditApi } = await import("../../api/audit");
    vi.mocked(auditApi.list).mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    } as AuditListResponse);

    renderAudit();

    const heading = await screen.findByRole("heading", { name: /auditoría/i });
    expect(heading).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay eventos", async () => {
    const { auditApi } = await import("../../api/audit");
    vi.mocked(auditApi.list).mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    } as AuditListResponse);

    renderAudit();

    const emptyText = await screen.findByText(/no hay eventos registrados/i);
    expect(emptyText).toBeInTheDocument();
  });

  it("muestra un evento en la tabla", async () => {
    const { auditApi } = await import("../../api/audit");
    vi.mocked(auditApi.list).mockResolvedValueOnce({
      items: [
        {
          id: "e1",
          actor_id: "u1",
          action_type: "doctor_created",
          entity_type: "doctor",
          entity_id: "d1",
          occurred_at: "2026-05-01T10:00:00",
          before_snapshot: null,
          after_snapshot: { name: "Dr. López" },
          metadata_: null,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    } as AuditListResponse);

    renderAudit();

    const actionLabel = await screen.findByText("Médico creado");
    expect(actionLabel).toBeInTheDocument();

    const entityLabel = screen.getByText("Médico");
    expect(entityLabel).toBeInTheDocument();
  });
});
