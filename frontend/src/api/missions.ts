import { apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MissionCandidateRankingEntry {
  id: string;
  doctor_id: string;
  doctor_name: string | null;
  ranking_position: number;
  total_load_score: number;
  monthly_service_load: number;
  recent_service_load: number;
  monthly_mission_load: number;
  eligible: boolean;
  reasons: Record<string, unknown> | null;
  warnings: unknown[] | null;
}

export interface MissionCandidateRanking {
  id: string;
  month: number;
  year: number;
  calendar_version_id: string | null;
  generated_at: string;
  created_by: string | null;
  entries: MissionCandidateRankingEntry[];
}

export interface MissionParticipant {
  id: string;
  mission_assignment_id: string;
  doctor_id: string;
  doctor_name: string | null;
  selection_source: string;
  ranking_position: number | null;
  score: number | null;
  created_at: string;
}

export interface MissionAssignment {
  id: string;
  mission_date: string;
  mission_start_at: string | null;
  mission_end_at: string | null;
  participant_count: number;
  location: string | null;
  description: string | null;
  status: string;
  source: string;
  created_by: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  participants: MissionParticipant[];
}

export interface MissionCandidateResponse {
  mission_date: string;
  participant_count: number;
  primary: MissionCandidateRankingEntry[];
  alternates: MissionCandidateRankingEntry[];
}

export interface MissionCandidateDateRankingEntry extends Omit<MissionCandidateRankingEntry, "reasons" | "warnings"> {
  adjusted_position: number;
  recommendation_status: "recommended" | "alternate" | "unavailable";
  selectable: boolean;
  reasons: string[];
  warnings: string[];
}

export interface MissionCandidateDateRankingResponse {
  mission_date: string;
  month: number;
  year: number;
  entries: MissionCandidateDateRankingEntry[];
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const missionsApi = {
  generateRanking: (year: number, month: number) =>
    apiFetch<MissionCandidateRanking>("/missions/rankings/generate", {
      method: "POST",
      body: JSON.stringify({ year, month }),
    }),

  getRanking: (year: number, month: number) =>
    apiFetch<MissionCandidateRanking>(`/missions/rankings/${year}/${month}`),

  listMissions: () =>
    apiFetch<MissionAssignment[]>("/missions"),

  createMission: (
    date: string,
    participantCount: number,
    location?: string,
    description?: string,
  ) =>
    apiFetch<MissionAssignment>("/missions", {
      method: "POST",
      body: JSON.stringify({
        mission_date: date,
        participant_count: participantCount,
        location: location ?? null,
        description: description ?? null,
      }),
    }),

  confirmMission: (missionId: string, doctorIds: string[]) =>
    apiFetch<MissionAssignment>(`/missions/${missionId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ doctor_ids: doctorIds }),
    }),

  updateMission: (
    missionId: string,
    payload: {
      mission_date?: string;
      participant_count?: number;
      location?: string | null;
      description?: string | null;
      mission_start_at?: string | null;
      mission_end_at?: string | null;
    },
  ) =>
    apiFetch<MissionAssignment>(`/missions/${missionId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteMission: (missionId: string) =>
    apiFetch<void>(`/missions/${missionId}`, {
      method: "DELETE",
    }),

  getCandidates: (
    missionDate: string,
    participantCount: number,
    includeAlternates = false,
  ) =>
    apiFetch<MissionCandidateResponse>("/missions/candidates", {
      method: "POST",
      body: JSON.stringify({
        mission_date: missionDate,
        participant_count: participantCount,
        include_alternates: includeAlternates,
      }),
    }),

  getRankedCandidatesForDate: (missionDate: string) =>
    apiFetch<MissionCandidateDateRankingResponse>("/missions/candidates/ranked", {
      method: "POST",
      body: JSON.stringify({
        mission_date: missionDate,
        participant_count: 1,
        include_alternates: true,
      }),
    }),
};
