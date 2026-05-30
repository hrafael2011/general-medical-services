import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MissionView } from "./MissionView";
import { ApiError } from "../../api/client";

vi.mock("../../api/missions", () => ({
  missionsApi: {
    listMissions: vi.fn(),
    getRanking: vi.fn(),
    generateRanking: vi.fn(),
    createMission: vi.fn(),
    updateMission: vi.fn(),
    deleteMission: vi.fn(),
    confirmMission: vi.fn(),
    getCandidates: vi.fn(),
    getRankedCandidatesForDate: vi.fn(),
  },
}));

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: vi.fn(),
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
  beforeEach(async () => {
    vi.clearAllMocks();
    const { doctorsApi } = await import("../../api/doctors");
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(doctorsApi.list).mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.mocked(missionsApi.listMissions).mockResolvedValue([]);
    vi.mocked(missionsApi.getRanking).mockResolvedValue({
      id: "ranking-empty",
      month: new Date().getMonth() + 1,
      year: new Date().getFullYear(),
      calendar_version_id: "version-approved",
      generated_at: "2026-05-01T00:00:00",
      created_by: null,
      entries: [],
    });
  });

  it("muestra el título y la sección de ranking", async () => {
    renderMissions();

    expect(await screen.findByRole("heading", { name: /misiones/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(/ranking de candidatos/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /generar ranking/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ver existente/i })).not.toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay misiones", async () => {
    renderMissions();

    expect(await screen.findByText(/no hay misiones registradas/i)).toBeInTheDocument();
  });

  it("muestra la misión en la tabla", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([
      {
        id: "m1",
        mission_date: "2026-06-15",
        mission_start_at: null,
        mission_end_at: null,
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
        deleted_at: null,
        has_replacement_warnings: false,
        replacement_warning_count: 0,
        participants: [],
      },
    ]);

    renderMissions();

    expect(await screen.findByText("2026-06-15")).toBeInTheDocument();
    expect(screen.getByText("Base Norte")).toBeInTheDocument();
  });

  it("muestra advertencia de reemplazo pendiente en gestión de misiones", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([
      {
        id: "m-warning",
        mission_date: "2026-06-20",
        mission_start_at: null,
        mission_end_at: null,
        participant_count: 1,
        location: "Base Norte",
        description: null,
        status: "confirmed",
        source: "manual",
        created_by: null,
        confirmed_by: null,
        confirmed_at: "2026-05-01T00:00:00",
        created_at: "2026-05-01T00:00:00",
        updated_at: "2026-05-01T00:00:00",
        deleted_at: null,
        has_replacement_warnings: true,
        replacement_warning_count: 1,
        participants: [
          {
            id: "p1",
            mission_assignment_id: "m-warning",
            doctor_id: "d1",
            doctor_name: "Dr. Inactivo",
            selection_source: "manual",
            ranking_position: null,
            score: null,
            created_at: "2026-05-01T00:00:00",
            requires_replacement: true,
            replacement_reason: "Médico inactivo para servicio.",
          },
        ],
      },
    ]);

    renderMissions();

    expect(await screen.findByText("1 reemplazo pendiente")).toBeInTheDocument();
    expect(screen.getByText(/Dr\. Inactivo: Médico inactivo para servicio/i)).toBeInTheDocument();
  });

  it("abre el formulario de creación dentro de gestión sin ocultar la tabla", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([
      {
        id: "m1",
        mission_date: "2026-06-15",
        mission_start_at: null,
        mission_end_at: null,
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
        deleted_at: null,
        has_replacement_warnings: false,
        replacement_warning_count: 0,
        participants: [],
      },
    ]);

    renderMissions();
    fireEvent.click(await screen.findByRole("button", { name: /^crear misión$/i }));

    expect(screen.getByLabelText(/fecha/i)).toBeInTheDocument();
    expect(screen.getByText("2026-06-15")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^crear misión$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ocultar creación/i })).toBeInTheDocument();
  });

  it("muestra solo elegibles disponibles en confirmación", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([
      {
        id: "m1",
        mission_date: "2026-06-12",
        mission_start_at: null,
        mission_end_at: null,
        participant_count: 2,
        location: "Base Norte",
        description: null,
        status: "draft",
        source: "manual",
        created_by: null,
        confirmed_by: null,
        confirmed_at: null,
        created_at: "2026-05-01T00:00:00",
        updated_at: "2026-05-01T00:00:00",
        deleted_at: null,
        has_replacement_warnings: false,
        replacement_warning_count: 0,
        participants: [],
      },
    ]);
    vi.mocked(missionsApi.getRankedCandidatesForDate).mockResolvedValueOnce({
      mission_date: "2026-06-12",
      month: 6,
      year: 2026,
      entries: [
        {
          id: "entry-1",
          doctor_id: "uuid-ok",
          doctor_name: "Dra. Recomendada",
          ranking_position: 1,
          adjusted_position: 1,
          recommendation_status: "recommended",
          selectable: true,
          total_load_score: 0,
          monthly_service_load: 0,
          recent_service_load: 0,
          monthly_mission_load: 0,
          eligible: true,
          reasons: [],
          warnings: [],
        },
      ],
    });

    renderMissions();
    fireEvent.click(await screen.findByRole("button", { name: /confirmar/i }));

    expect(await screen.findByText("Dra. Recomendada")).toBeInTheDocument();
    expect(screen.getByText(/elegibles disponibles/i)).toBeInTheDocument();
    expect(screen.queryByText("uuid-ok")).not.toBeInTheDocument();
    expect(screen.queryByText("Dr. Con Servicio")).not.toBeInTheDocument();
  });

  it("muestra nombres en el ranking y no UUIDs", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([]);
    vi.mocked(missionsApi.getRanking).mockResolvedValueOnce({
      id: "ranking-1",
      month: new Date().getMonth() + 1,
      year: new Date().getFullYear(),
      calendar_version_id: null,
      generated_at: "2026-05-01T00:00:00",
      created_by: null,
      entries: [
        {
          id: "entry-1",
          doctor_id: "doctor-uuid-hidden",
          doctor_name: "Dra. Ana Perez",
          ranking_position: 1,
          total_load_score: 0,
          monthly_service_load: 0,
          recent_service_load: 0,
          monthly_mission_load: 0,
          eligible: true,
          reasons: null,
          warnings: null,
        },
      ],
    });

    renderMissions();
    fireEvent.click(await screen.findByRole("button", { name: /ranking de candidatos/i }));

    expect(await screen.findByText("Dra. Ana Perez")).toBeInTheDocument();
    expect(screen.queryByText("doctor-uuid-hidden")).not.toBeInTheDocument();
    expect(screen.queryByText(/doctor id/i)).not.toBeInTheDocument();
  });

  it("resuelve el nombre desde doctores cuando el ranking llega sin doctor_name", async () => {
    const { missionsApi } = await import("../../api/missions");
    const { doctorsApi } = await import("../../api/doctors");
    vi.mocked(missionsApi.listMissions).mockResolvedValueOnce([]);
    vi.mocked(doctorsApi.list).mockResolvedValueOnce({
      total: 1,
      items: [
        {
          id: "doctor-uuid-hidden",
          name: "Dra. Nombre Resuelto",
          sex: "female",
          rank_id: null,
          department_id: null,
          notes: null,
          active: true,
          service_active: true,
          service_inactive_reason_id: null,
          service_inactive_detail: null,
          participa_misiones: true,
          whatsapp_phone: null,
          monthly_service_target: 3,
          monthly_service_max: 3,
          monthly_service_limit_mode: "hard",
          availability_mode: "monthly",
          allowed_area_ids: [],
        },
      ],
    });
    vi.mocked(missionsApi.getRanking).mockResolvedValueOnce({
      id: "ranking-1",
      month: new Date().getMonth() + 1,
      year: new Date().getFullYear(),
      calendar_version_id: null,
      generated_at: "2026-05-01T00:00:00",
      created_by: null,
      entries: [
        {
          id: "entry-1",
          doctor_id: "doctor-uuid-hidden",
          doctor_name: null,
          ranking_position: 1,
          total_load_score: 0,
          monthly_service_load: 0,
          recent_service_load: 0,
          monthly_mission_load: 0,
          eligible: true,
          reasons: null,
          warnings: null,
        },
      ],
    });

    renderMissions();
    fireEvent.click(await screen.findByRole("button", { name: /ranking de candidatos/i }));

    expect(await screen.findByText("Dra. Nombre Resuelto")).toBeInTheDocument();
    expect(screen.queryByText("doctor-uuid-hidden")).not.toBeInTheDocument();
  });

  it("muestra mensaje claro cuando no hay calendario aprobado", async () => {
    const { missionsApi } = await import("../../api/missions");
    vi.mocked(missionsApi.getRanking).mockRejectedValueOnce(
      new ApiError(409, {
        code: "approved_calendar_required",
        message: "No hay calendario aprobado.",
      }),
    );

    renderMissions();
    fireEvent.click(await screen.findByRole("button", { name: /ranking de candidatos/i }));

    expect(await screen.findByText(/no tiene calendario aprobado/i)).toBeInTheDocument();
  });
});
