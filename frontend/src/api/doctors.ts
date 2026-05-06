import { apiFetch } from "./client";

export interface DoctorRead {
  id: string; name: string; sex: string;
  rank_id: string | null; department_id: string | null;
  phone: string | null; notes: string | null;
  active: boolean; service_active: boolean;
  service_inactive_reason_id: string | null;
  service_inactive_detail: string | null;
  participa_misiones: boolean;
  whatsapp_phone: string | null;
  monthly_service_target: number; monthly_service_max: number;
  monthly_service_limit_mode: string; availability_mode: string;
  allowed_area_ids: string[];
}

export interface DoctorListResponse { items: DoctorRead[]; total: number; }

export interface CreateDoctorPayload {
  name: string; sex: string;
  rank_id?: string | null; department_id?: string | null;
  phone?: string | null; notes?: string | null;
  participa_misiones: boolean;
  whatsapp_phone?: string | null;
  monthly_service_target: number; monthly_service_max: number;
  monthly_service_limit_mode: string; availability_mode: string;
  allowed_area_ids: string[];
}

export interface ServiceAreaRead { id: string; code: string; display_name: string; active: boolean; }
export interface RankRead { id: string; name: string; abbreviation: string; }

export const doctorsApi = {
  list: (activeOnly = false) =>
    apiFetch<DoctorListResponse>(`/doctors?active_only=${activeOnly}`),
  get: (id: string) => apiFetch<DoctorRead>(`/doctors/${id}`),
  create: (payload: CreateDoctorPayload) =>
    apiFetch<DoctorRead>("/doctors", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<CreateDoctorPayload>) =>
    apiFetch<DoctorRead>(`/doctors/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deactivateService: (id: string, reason_id: string, detail?: string) =>
    apiFetch<DoctorRead>(`/doctors/${id}/deactivate-service`, {
      method: "POST", body: JSON.stringify({ reason_id, detail }),
    }),
  reactivateService: (id: string) =>
    apiFetch<DoctorRead>(`/doctors/${id}/reactivate-service`, { method: "POST" }),
  listServiceAreas: () => apiFetch<ServiceAreaRead[]>("/catalogs/service-areas"),
  listRanks: () => apiFetch<RankRead[]>("/catalogs/ranks"),
};
