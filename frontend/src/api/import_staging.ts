import { apiFetch } from "./client";
import { getToken } from "./client";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface ImportSourceFile {
  id: string;
  file_name: string;
  file_type: string;
  checksum: string;
  detected_period_year: number | null;
  detected_period_month: number | null;
  imported_by: string | null;
  imported_at: string;
  status: string;
  record_count: number;
  error_message: string | null;
}

export interface ImportStagedRecord {
  id: string;
  source_file_id: string;
  record_type: string;
  raw_value: string | null;
  parsed_value: Record<string, unknown> | null;
  normalized_value: Record<string, unknown> | null;
  confidence: number | null;
  parser_rule: string | null;
  match_status: string | null;
  matched_doctor_id: string | null;
  review_status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  applied_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface ImportQualityReport {
  source_file_id: string;
  file_name: string;
  total_raw_extractions: number;
  total_staged: number;
  exact_matches: number;
  probable_matches: number;
  possible_matches: number;
  new_candidates: number;
  conflicts: number;
  low_confidence: number;
  pending_review: number;
  approved: number;
  rejected: number;
  applied: number;
}

export const importApi = {
  async uploadFile(
    file: File,
    year?: number,
    month?: number,
  ): Promise<ImportQualityReport | { ignored: boolean; reason: string }> {
    const formData = new FormData();
    formData.append("file", file);

    const params = new URLSearchParams();
    if (year !== undefined) params.set("year", String(year));
    if (month !== undefined) params.set("month", String(month));
    const qs = params.toString() ? `?${params.toString()}` : "";

    const token = getToken();
    const headers: Record<string, string> = token
      ? { Authorization: `Bearer ${token}` }
      : {};

    const res = await fetch(`${BASE}/api/import/upload${qs}`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.detail ?? "Error del servidor");
    }
    return res.json() as Promise<ImportQualityReport | { ignored: boolean; reason: string }>;
  },

  listFiles(): Promise<{ items: ImportSourceFile[]; total: number }> {
    return apiFetch<{ items: ImportSourceFile[]; total: number }>("/import/files");
  },

  getQualityReport(fileId: string): Promise<ImportQualityReport> {
    return apiFetch<ImportQualityReport>(`/import/files/${fileId}/quality-report`);
  },

  listStaged(params: {
    source_file_id?: string;
    record_type?: string;
    review_status?: string;
    limit?: number;
  }): Promise<{ items: ImportStagedRecord[]; total: number }> {
    const qs = new URLSearchParams();
    if (params.source_file_id) qs.set("source_file_id", params.source_file_id);
    if (params.record_type) qs.set("record_type", params.record_type);
    if (params.review_status) qs.set("review_status", params.review_status);
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch<{ items: ImportStagedRecord[]; total: number }>(`/import/staged${query}`);
  },

  reviewRecord(
    recordId: string,
    action: string,
    notes?: string,
    matched_doctor_id?: string,
  ): Promise<ImportStagedRecord> {
    return apiFetch<ImportStagedRecord>(`/import/staged/${recordId}/review`, {
      method: "POST",
      body: JSON.stringify({ action, notes, matched_doctor_id }),
    });
  },

  applyApproved(source_file_id?: string): Promise<{ applied: number; skipped: number; errors: string[] }> {
    return apiFetch<{ applied: number; skipped: number; errors: string[] }>("/import/apply", {
      method: "POST",
      body: JSON.stringify({ source_file_id }),
    });
  },
};
