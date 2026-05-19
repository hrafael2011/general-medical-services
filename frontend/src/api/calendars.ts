import { apiFetch } from "./client";

export interface GenerationSlotResult {
  service_date: string;
  service_area_id: string;
  assigned_doctor_id: string | null;
  warnings: string[];
  score: number | null;
}

export interface GenerationResponse {
  version_id: string;
  calendar_id: string;
  month: number;
  year: number;
  calendar_status: "draft" | "partial" | "approved";
  generation_mode: CalendarRead["generation_mode"];
  review_required: boolean;
  total_slots: number;
  assigned_count: number;
  gap_count: number;
  slots: GenerationSlotResult[];
}

export interface CalendarRead {
  id: string;
  year: number;
  month: number;
  status: "draft" | "partial" | "approved";
  generation_mode: "manual" | "assisted_auto" | "scheduled_auto";
  created_by: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
}

export interface CalendarVersionRead {
  id: string;
  calendar_id: string;
  version_number: number;
  status: "draft" | "approved";
  created_by: string | null;
  reason: string | null;
  created_at: string;
}

export interface CalendarAssignmentRead {
  id: string;
  calendar_version_id: string;
  service_date: string;
  service_area_id: string;
  doctor_id: string;
  override_justification: string | null;
  assignment_source: string;
  rationale: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string;
}

export interface DaySlot {
  service_date: string;
  service_area_id: string;
  assignment: CalendarAssignmentRead | null;
  has_warning: boolean;
  warning_message: string | null;
}

export interface CalendarGridResponse {
  calendar: CalendarRead;
  version: CalendarVersionRead;
  slots: DaySlot[];
  gaps: Record<string, unknown>[];
}

export interface WeekRead {
  id: string;
  week_number: number;
  label: string;
  start_date: string;
  end_date: string;
  status: string;
  assignment_count: number;
  doctor_assignment_counts: { doctor_id: string; doctor_name: string; count: number }[];
  approved_by: string | null;
  approved_at: string | null;
}

export interface EligibleDoctorRead {
  id: string;
  full_name: string;
  specialty: string | null;
  rank_name: string | null;
}

export interface EligibleDoctorsResponse {
  doctors: EligibleDoctorRead[];
}

export interface HardBlockItem {
  code: string;
  description: string;
}

export interface WarningItem {
  code: string;
  description: string;
}

export interface EvaluationRequest {
  doctor_id: string;
  service_date: string;
  service_area_id: string;
}

export interface EvaluationResponse {
  hard_blocks: HardBlockItem[];
  warnings: WarningItem[];
}

export const calendarsApi = {
  list: () => apiFetch<CalendarRead[]>("/calendars"),

  create: (
    year: number,
    month: number,
    generationMode: CalendarRead["generation_mode"] = "manual",
  ) =>
    apiFetch<CalendarRead>("/calendars", {
      method: "POST",
      body: JSON.stringify({ year, month, generation_mode: generationMode }),
    }),

  getGrid: (calendarId: string) =>
    apiFetch<CalendarGridResponse>(`/calendars/${calendarId}/grid`),

  approve: (calendarId: string, reason?: string) =>
    apiFetch<CalendarVersionRead>(`/calendars/${calendarId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),

  unlock: (calendarId: string) =>
    apiFetch<CalendarVersionRead>(
      `/calendars/${calendarId}/unlock`,
      { method: "POST" },
    ),

  assignDoctor: (
    calendarId: string,
    versionId: string,
    payload: { service_date: string; service_area_id: string; doctor_id: string; override_justification?: string | null; force_warnings?: string[] | null },
  ) =>
    apiFetch<CalendarAssignmentRead>(
      `/calendars/${calendarId}/versions/${versionId}/assignments`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  removeAssignment: (calendarId: string, versionId: string, assignmentId: string) =>
    apiFetch<void>(
      `/calendars/${calendarId}/versions/${versionId}/assignments/${assignmentId}`,
      { method: "DELETE" },
    ),

  replaceAssignment: (
    calendarId: string,
    versionId: string,
    assignmentId: string,
    doctorId: string,
    overrideJustification?: string | null,
    forceWarnings?: string[] | null,
  ) =>
    apiFetch<CalendarAssignmentRead>(
      `/calendars/${calendarId}/versions/${versionId}/assignments/${assignmentId}`,
      { method: "PATCH", body: JSON.stringify({ doctor_id: doctorId, override_justification: overrideJustification ?? null, force_warnings: forceWarnings ?? null }) },
    ),

  generate: (calendarId: string) =>
    apiFetch<GenerationResponse>(`/calendars/${calendarId}/generate`, { method: "POST" }),

  delete: (calendarId: string) =>
    apiFetch<void>(`/calendars/${calendarId}`, { method: "DELETE" }),

  eligibleDoctors: (calendarId: string, date: string, areaId: string) =>
    apiFetch<EligibleDoctorsResponse>(
      `/calendars/${calendarId}/eligible-doctors?date=${date}&area_id=${areaId}`,
    ),

  evaluate: (calendarId: string, payload: EvaluationRequest) =>
    apiFetch<EvaluationResponse>(`/calendars/${calendarId}/evaluate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listWeeks: (calendarId: string) =>
    apiFetch<WeekRead[]>(`/calendars/${calendarId}/weeks`),

  approveWeek: (calendarId: string, weekId: string) =>
    apiFetch<WeekRead>(`/calendars/${calendarId}/weeks/${weekId}/approve`, {
      method: "POST",
    }),

  unlockWeek: (calendarId: string, weekId: string) =>
    apiFetch<WeekRead>(`/calendars/${calendarId}/weeks/${weekId}/unlock`, {
      method: "POST",
    }),

  exportWeeklyPDF: (calendarId: string, weekId: string) =>
    apiFetch<Blob>(
      `/reports/calendar/${calendarId}/weeks/${weekId}/pdf`,
      {},
      "blob",
    ),

  exportFullCalendarPDF: (calendarId: string) =>
    apiFetch<Blob>(
      `/reports/calendar/${calendarId}/full-pdf`,
      {},
      "blob",
    ),
};
