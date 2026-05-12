import { apiFetch } from "./client";

export interface CoverageByArea {
  area_id: string;
  area_name: string;
  days_covered: number;
  days_uncovered: number;
  coverage_pct: number;
  gaps: { date: string; day_name: string }[];
}

export interface CoverageResponse {
  period_label: string;
  overall_coverage_pct: number;
  total_gaps: number;
  most_critical_area: string | null;
  weakest_day: string | null;
  by_area: CoverageByArea[];
}

export interface WorkloadEntry {
  doctor_id: string;
  name: string;
  rank: string | null;
  sex: string | null;
  department: string | null;
  emergencia: number;
  pista: number;
  disponible: number;
  total: number;
  details: { date: string; area: string }[];
}

export interface WorkloadResponse {
  period_label: string;
  total_services: number;
  active_doctors: number;
  avg_per_doctor: number;
  most_load: { name: string; total: number } | null;
  least_load: { name: string; total: number } | null;
  entries: WorkloadEntry[];
}

export interface DossierResponse {
  doctor_id: string;
  name: string;
  rank: string | null;
  sex: string | null;
  department: string | null;
  areas: string[];
  period_label: string;
  total_services: number;
  services_by_area: Record<string, number>;
  avg_weekly: number;
  services: { date: string; day_name: string; area: string; source: string }[];
  missions: { mission: string; role: string; status: string }[];
  restrictions: { type: string; date: string | null; reason: string }[];
  availability: string[];
}

interface CoverageParams {
  year_start: number; month_start: number;
  year_end: number; month_end: number;
  area?: string; rank_id?: string; sex?: string; department_id?: string;
}

interface WorkloadParams {
  year: number; month: number;
  area?: string; rank_id?: string; sex?: string; department_id?: string;
  group_by?: string; order_by?: string;
}

export const reportsApi = {
  getCoverage(params: CoverageParams): Promise<CoverageResponse> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)); });
    return apiFetch<CoverageResponse>(`/reports/coverage?${q}`);
  },

  getCoveragePdf(params: CoverageParams): Promise<Blob> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)); });
    q.set("format", "pdf");
    return apiFetch<Blob>(`/reports/coverage?${q}`, undefined, "blob");
  },

  getWorkload(params: WorkloadParams): Promise<WorkloadResponse> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)); });
    return apiFetch<WorkloadResponse>(`/reports/workload?${q}`);
  },

  getWorkloadPdf(params: WorkloadParams): Promise<Blob> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)); });
    q.set("format", "pdf");
    return apiFetch<Blob>(`/reports/workload?${q}`, undefined, "blob");
  },

  getDoctorDossier(doctorId: string, dateFrom?: string, dateTo?: string): Promise<DossierResponse> {
    const q = new URLSearchParams();
    if (dateFrom) q.set("date_from", dateFrom);
    if (dateTo) q.set("date_to", dateTo);
    return apiFetch<DossierResponse>(`/reports/doctor-dossier/${doctorId}?${q}`);
  },

  getDoctorDossierPdf(doctorId: string, dateFrom?: string, dateTo?: string): Promise<Blob> {
    const q = new URLSearchParams();
    if (dateFrom) q.set("date_from", dateFrom);
    if (dateTo) q.set("date_to", dateTo);
    q.set("format", "pdf");
    return apiFetch<Blob>(`/reports/doctor-dossier/${doctorId}?${q}`, undefined, "blob");
  },
};
