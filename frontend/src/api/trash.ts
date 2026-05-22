import { apiFetch } from "./client";

export interface TrashItem {
  id: string;
  name: string;
  deleted_at: string;
  rank_name?: string;
  email?: string;
  role?: string;
  abbreviation?: string;
  normalized_name?: string;
}

export interface TrashCounts {
  doctors: number;
  users: number;
  ranks: number;
  departments: number;
}

export const trashApi = {
  list: (type: string) =>
    apiFetch<TrashItem[]>(`/admin/trash?type=${type}`),
  counts: () =>
    apiFetch<TrashCounts>("/admin/trash/counts"),
  restore: (type: string, id: string) =>
    apiFetch<void>(`/admin/trash/${type}/${id}/restore`, { method: "POST" }),
  hardDelete: (type: string, id: string) =>
    apiFetch<void>(`/admin/trash/${type}/${id}`, { method: "DELETE" }),
};
