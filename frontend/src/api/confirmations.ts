import { apiFetch } from "./client";

export interface ProcessOverdueConfirmationsResponse {
  expired: number;
  alerts_created: number;
}

export interface PublicConfirmationRead {
  confirmation_type: string;
  status: string;
  doctor_name: string | null;
  due_at: string | null;
  responded_at: string | null;
}

export interface PublicConfirmationResponse {
  confirmation_type: string;
  status: string;
  doctor_name: string | null;
  responded_at: string | null;
}

export interface ConfirmationRequestRead {
  id: string;
  confirmation_type: string;
  status: string;
  doctor_id: string;
  doctor_name?: string;
  assignment_id: string | null;
  due_at: string | null;
  responded_at: string | null;
  response_channel: string | null;
  response_payload?: Record<string, unknown> | null;
  created_at: string;
  escalated_at: string | null;
}

export interface ConfirmationRequestListResponse {
  items: ConfirmationRequestRead[];
  total: number;
}

export const confirmationsApi = {
  list: (params?: { status?: string; doctor_id?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.doctor_id) q.set("doctor_id", params.doctor_id);
    if (params?.limit) q.set("limit", String(params.limit));
    return apiFetch<ConfirmationRequestListResponse>(`/confirmation-requests?${q}`);
  },

  processOverdue: () =>
    apiFetch<ProcessOverdueConfirmationsResponse>(
      "/confirmation-requests/process-overdue",
      { method: "POST" },
    ),

  getPublicConfirmation: (token: string) =>
    apiFetch<PublicConfirmationRead>(
      `/confirmation-requests/public/${encodeURIComponent(token)}`,
    ),

  respondPublicConfirmation: (token: string, action: "received" | "confirm", note?: string) =>
    apiFetch<PublicConfirmationResponse>(
      `/confirmation-requests/public/${encodeURIComponent(token)}/${action}`,
      {
        method: "POST",
        body: JSON.stringify({ note: note?.trim() || null }),
      },
    ),
};
