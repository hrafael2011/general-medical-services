import { apiFetch } from "./client";

export interface AuditEventRead {
  id: string;
  actor_id: string | null;
  actor_display?: string | null;
  action_type: string;
  entity_type: string;
  entity_id: string | null;
  entity_display?: string | null;
  occurred_at: string;
  request_id?: string | null;
  before_snapshot: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown> | null;
  metadata_: Record<string, unknown> | null;
  detail_summary?: string | null;
}

export interface AuditListResponse {
  items: AuditEventRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditFilters {
  actor_id?: string;
  action_type?: string;
  entity_type?: string;
  entity_id?: string;
  limit?: number;
  offset?: number;
}

export const auditApi = {
  list: (filters: AuditFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.actor_id) params.set("actor_id", filters.actor_id);
    if (filters.action_type) params.set("action_type", filters.action_type);
    if (filters.entity_type) params.set("entity_type", filters.entity_type);
    if (filters.entity_id) params.set("entity_id", filters.entity_id);
    params.set("limit", String(filters.limit ?? 50));
    params.set("offset", String(filters.offset ?? 0));
    return apiFetch<AuditListResponse>(`/audit?${params.toString()}`);
  },
};
