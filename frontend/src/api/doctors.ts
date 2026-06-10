import { apiFetch } from "./client";

export interface DoctorRead {
  id: string; first_name?: string | null; last_name?: string | null;
  name: string; sex: string;
  rank_id: string | null; department_id: string | null;
  notes: string | null;
  active: boolean; service_active: boolean;
  service_inactive_reason_id: string | null;
  service_inactive_detail: string | null;
  participa_misiones: boolean;
  whatsapp_phone: string | null;
  monthly_service_target: number; monthly_service_max: number;
  monthly_service_limit_mode: string; availability_mode: string;
  allowed_area_ids: string[];
  removed_assignments?: number | null;
  affected_calendar_ids?: string[] | null;
}

export interface DoctorListResponse { items: DoctorRead[]; total: number; }

export interface CreateDoctorPayload {
  first_name?: string | null; last_name?: string | null;
  name?: string; sex: string;
  rank_id?: string | null; department_id?: string | null;
  notes?: string | null;
  participa_misiones: boolean;
  service_active?: boolean;  // <-- ADD THIS
  whatsapp_phone?: string | null;
  monthly_service_target: number; monthly_service_max: number;
  monthly_service_limit_mode: string; availability_mode: string;
  allowed_area_ids: string[];
}

export interface ServiceAreaRead { id: string; code: string; display_name: string; active: boolean; }
export interface RankRead { id: string; name: string; abbreviation: string; active: boolean; }
export interface DepartmentRead { id: string; name: string; normalized_name: string; active: boolean; }
export interface DeactivationReasonRead {
  id: string;
  code: string;
  display_name: string;
  active: boolean;
  requires_detail: boolean;
  applies_to_sex: string | null;
  severity: string;
}

export interface DeactivationReasonPayload {
  display_name: string;
  applies_to_sex: string | null;
  active?: boolean;
}

export interface AvailabilityRead {
  id: string;
  doctor_id: string;
  availability_type: string;
  days_of_week: number[] | null;
  available_dates: number[] | null;
  weekday: number | null;
  week_number: number | null;
  year: number | null;
  month: number | null;
}

export const doctorsApi = {
  list: (activeOnly = false) =>
    apiFetch<DoctorListResponse>(`/doctors?active_only=${activeOnly}`),
  get: (id: string) => apiFetch<DoctorRead>(`/doctors/${id}`),
  create: (payload: CreateDoctorPayload) =>
    apiFetch<DoctorRead>("/doctors", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<CreateDoctorPayload>) =>
    apiFetch<DoctorRead>(`/doctors/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: string) =>
    apiFetch<void>(`/doctors/${id}`, { method: "DELETE" }),
  deactivateService: (id: string, reason_id: string, detail?: string) =>
    apiFetch<DoctorRead>(`/doctors/${id}/deactivate-service`, {
      method: "POST", body: JSON.stringify({ reason_id, detail }),
    }),
  reactivateService: (id: string) =>
    apiFetch<DoctorRead>(`/doctors/${id}/reactivate-service`, { method: "POST" }),
  listServiceAreas: () => apiFetch<ServiceAreaRead[]>("/catalogs/service-areas"),
  listRanks: () => apiFetch<RankRead[]>("/catalogs/ranks"),
  createRank: (name: string, abbreviation: string) =>
    apiFetch<RankRead>("/catalogs/ranks", {
      method: "POST", body: JSON.stringify({ name, abbreviation }),
    }),
  updateRank: (id: string, payload: { name?: string; abbreviation?: string; active?: boolean }) =>
    apiFetch<RankRead>(`/catalogs/ranks/${id}`, {
      method: "PATCH", body: JSON.stringify(payload),
    }),
  deleteRank: (id: string) =>
    apiFetch<void>(`/catalogs/ranks/${id}`, { method: "DELETE" }),
  listDepartments: () => apiFetch<DepartmentRead[]>("/catalogs/departments"),
  createDepartment: (name: string) =>
    apiFetch<DepartmentRead>("/catalogs/departments", {
      method: "POST", body: JSON.stringify({ name }),
    }),
  updateDepartment: (id: string, payload: { name?: string; active?: boolean }) =>
    apiFetch<DepartmentRead>(`/catalogs/departments/${id}`, {
      method: "PATCH", body: JSON.stringify(payload),
    }),
  deleteDepartment: (id: string) =>
    apiFetch<void>(`/catalogs/departments/${id}`, { method: "DELETE" }),
  listDeactivationReasons: (sex?: string) =>
    apiFetch<DeactivationReasonRead[]>(
      `/catalogs/deactivation-reasons${sex ? `?sex=${sex}` : ""}`
    ),
  createDeactivationReason: (payload: DeactivationReasonPayload) =>
    apiFetch<DeactivationReasonRead>("/catalogs/deactivation-reasons", {
      method: "POST", body: JSON.stringify(payload),
    }),
  updateDeactivationReason: (id: string, payload: Partial<DeactivationReasonPayload>) =>
    apiFetch<DeactivationReasonRead>(`/catalogs/deactivation-reasons/${id}`, {
      method: "PATCH", body: JSON.stringify(payload),
    }),
  deleteDeactivationReason: (id: string) =>
    apiFetch<{ message: string; affected_doctors: number }>(
      `/catalogs/deactivation-reasons/${id}`,
      { method: "DELETE" },
    ),
  listByDay: () =>
    apiFetch<DoctorByDayResponse>("/doctors/by-day"),
  listByArea: () =>
    apiFetch<DoctorByAreaResponse>("/doctors/by-area"),
  listByDepartment: () =>
    apiFetch<DoctorByDepartmentResponse>("/doctors/by-department"),
};

export interface DoctorByDayItem {
  id: string;
  name: string;
  rank_name: string | null;
  department_name: string | null;
  whatsapp_phone: string | null;
  recurring_tag: string | null;
}

export interface DayGroup {
  label: string;
  count: number;
  doctors: DoctorByDayItem[];
}

export interface DoctorByDayResponse {
  days: Record<string, DayGroup>;
}

export interface DoctorByAreaItem {
  id: string;
  name: string;
  rank_name: string | null;
  department_name: string | null;
}

export interface AreaGroup {
  area_id: string;
  code: string;
  label: string;
  count: number;
  doctors: DoctorByAreaItem[];
}

export interface DoctorByAreaResponse {
  areas: Record<string, AreaGroup>;
}

export interface DoctorByDepartmentItem {
  id: string;
  name: string;
  rank_name: string | null;
  department_name: string | null;
}

export interface DepartmentGroup {
  department_id: string;
  label: string;
  count: number;
  doctors: DoctorByDepartmentItem[];
}

export interface DoctorByDepartmentResponse {
  departments: Record<string, DepartmentGroup>;
}

export const availabilityApi = {
  setWeekly: (doctorId: string, body: { days_of_week: number[]; effective_from?: string; effective_to?: string }) =>
    apiFetch<unknown>(`/availability/doctors/${doctorId}/weekly`, { method: "POST", body: JSON.stringify(body) }),
  setMonthly: (doctorId: string, body: { year: number; month: number; available_dates: number[] }) =>
    apiFetch<unknown>(`/availability/doctors/${doctorId}/monthly`, { method: "POST", body: JSON.stringify(body) }),
  setRecurring: (doctorId: string, body: { weekday: number; week_number: number }) =>
    apiFetch<unknown>(`/availability/doctors/${doctorId}/recurring`, { method: "POST", body: JSON.stringify(body) }),
  list: (doctorId: string) =>
    apiFetch<AvailabilityRead[]>(`/availability/doctors/${doctorId}`),
  availableDoctors: (date: string) =>
    apiFetch<string[]>(`/availability/available-doctors?date=${date}`),
};
