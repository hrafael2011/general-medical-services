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

export const confirmationsApi = {
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
