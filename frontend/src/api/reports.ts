import { apiFetch } from "./client";
import { getToken } from "./client";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface OperationalSummary {
  period: { year: number; month: number };
  active_doctors: number;
  calendar_status: string | null;
  total_assignments: number;
  unresolved_gaps: number;
  generated_at: string;
}

export interface NotificationsSummary {
  period: { year: number; month: number };
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  generated_at: string;
}

async function fetchBlob(path: string): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  const res = await fetch(`${BASE}/api${path}`, { headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? "Error del servidor");
  }
  return res.blob();
}

export const reportsApi = {
  downloadCalendarExcel(calendarId: string): Promise<Blob> {
    return fetchBlob(`/reports/calendar/${calendarId}/excel`);
  },

  downloadDoctorHistoryExcel(year: number, month: number): Promise<Blob> {
    return fetchBlob(`/reports/doctor-history/excel?year=${year}&month=${month}`);
  },

  getNotificationsSummary(year: number, month: number): Promise<NotificationsSummary> {
    return apiFetch<NotificationsSummary>(
      `/reports/notifications-summary?year=${year}&month=${month}`,
    );
  },

  getOperationalSummary(year: number, month: number): Promise<OperationalSummary> {
    return apiFetch<OperationalSummary>(
      `/reports/operational-summary?year=${year}&month=${month}`,
    );
  },
};
