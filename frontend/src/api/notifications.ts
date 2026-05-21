import { apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NotificationEventRead {
  id: string;
  notification_type: string;
  recipient_doctor_id: string | null;
  recipient_phone: string | null;
  assignment_id: string | null;
  mission_id: string | null;
  scheduled_for: string | null;
  sent_at: string | null;
  status: string; // pending | sent | failed | cancelled
  provider: string | null;
  provider_message_id: string | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  payload: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationListResponse {
  items: NotificationEventRead[];
  total: number;
}

export interface ProcessNotificationsResponse {
  sent: number;
  failed: number;
  skipped: number;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const notificationsApi = {
  list: (status?: string, type?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (type) params.set("notification_type", type);
    const qs = params.toString();
    return apiFetch<NotificationListResponse>(`/notifications${qs ? `?${qs}` : ""}`);
  },
  process: () =>
    apiFetch<ProcessNotificationsResponse>("/notifications/process", { method: "POST" }),
};
