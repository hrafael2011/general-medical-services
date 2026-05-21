import { apiFetch } from "./client";

export interface ActionAlertRead {
  id: string;
  alert_type: string;
  section: string;
  severity: string;
  status: string;
  title: string;
  message: string;
  entity_type: string | null;
  entity_id: string | null;
  action_url: string | null;
  alert_metadata: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  dismissed_at: string | null;
  dismissed_by: string | null;
}

export interface ActionAlertListResponse {
  items: ActionAlertRead[];
  total: number;
}

export interface ActionAlertSummaryResponse {
  total_open: number;
  by_section: Record<string, number>;
}

export const actionAlertsApi = {
  list: (status = "open", limit = 20) => {
    const params = new URLSearchParams({ status, limit: String(limit) });
    return apiFetch<ActionAlertListResponse>(`/action-alerts?${params.toString()}`);
  },
  summary: () => apiFetch<ActionAlertSummaryResponse>("/action-alerts/summary"),
  resolve: (id: string) =>
    apiFetch<ActionAlertRead>(`/action-alerts/${id}/resolve`, { method: "POST" }),
  dismiss: (id: string) =>
    apiFetch<ActionAlertRead>(`/action-alerts/${id}/dismiss`, { method: "POST" }),
};
