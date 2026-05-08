import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MissionView } from "./MissionView";

vi.mock("../../api/missions", () => ({
  missionsApi: {
    listMissions: vi.fn(),
    getRanking: vi.fn(),
    generateRanking: vi.fn(),
    createMission: vi.fn(),
    confirmMission: vi.fn(),
    getCandidates: vi.fn(),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function renderMissions() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MissionView /></QueryClientProvider>);
}

describe("MissionView", () => {
  it("muestra el título y la sección de ranking", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([]);

    renderMissions();

    expect(await screen.findByRole("heading", { name: /misiones/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(/ranking de candidatos/i)).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay misiones", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([]);

    renderMissions();

    expect(await screen.findByText(/no hay misiones registradas/i)).toBeInTheDocument();
  });

  it("muestra la misión en la tabla", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([
      {
        id: "m1",
        mission_date: "2026-06-15",
        participant_count: 3,
        location: "Base Norte",
        description: null,
        status: "draft",
        source: "manual",
        created_by: null,
        confirmed_by: null,
        confirmed_at: null,
        created_at: "2026-05-01T00:00:00",
        updated_at: "2026-05-01T00:00:00",
        participants: [],
      },
    ]);

    renderMissions();

    expect(await screen.findByText("2026-06-15")).toBeInTheDocument();
    expect(screen.getByText("Base Norte")).toBeInTheDocument();
  });
});
