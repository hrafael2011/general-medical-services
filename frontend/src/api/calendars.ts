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
  calendar_status: "draft" | "approved";
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
  status: "draft" | "approved";
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

export interface CalendarGenerationSettings {
  auto_generation_enabled: boolean;
  generation_day: number;
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

  newVersion: (calendarId: string, reason?: string) =>
    apiFetch<CalendarVersionRead>(
      `/calendars/${calendarId}/new-version${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`,
      { method: "POST" },
    ),

  assignDoctor: (
    calendarId: string,
    versionId: string,
    payload: { service_date: string; service_area_id: string; doctor_id: string; override_justification?: string | null },
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
  ) =>
    apiFetch<CalendarAssignmentRead>(
      `/calendars/${calendarId}/versions/${versionId}/assignments/${assignmentId}`,
      { method: "PATCH", body: JSON.stringify({ doctor_id: doctorId, override_justification: overrideJustification ?? null }) },
    ),

  generate: (calendarId: string) =>
    apiFetch<GenerationResponse>(`/calendars/${calendarId}/generate`, { method: "POST" }),

  delete: (calendarId: string) =>
    apiFetch<void>(`/calendars/${calendarId}`, { method: "DELETE" }),

  getGenerationSettings: () =>
    apiFetch<CalendarGenerationSettings>("/catalogs/settings/calendar-generation"),

  updateGenerationSettings: (payload: Partial<CalendarGenerationSettings>) =>
    apiFetch<CalendarGenerationSettings>("/catalogs/settings/calendar-generation", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};
