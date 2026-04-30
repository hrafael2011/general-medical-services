import { Upload, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  importApi,
  ImportQualityReport,
  ImportSourceFile,
  ImportStagedRecord,
} from "../../api/import_staging";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-DO", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function reviewBadgeStyle(status: string): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "0.78rem",
    fontWeight: 600,
  };
  switch (status) {
    case "pending":
      return { ...base, background: "#f3f4f6", color: "#6b7280" };
    case "approved":
      return { ...base, background: "#d1fae5", color: "#065f46" };
    case "rejected":
      return { ...base, background: "#fee2e2", color: "#991b1b" };
    case "applied":
      return { ...base, background: "#dbeafe", color: "#1e40af" };
    default:
      return { ...base, background: "#f3f4f6", color: "#374151" };
  }
}

function statusBadgeStyle(status: string): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "0.78rem",
    fontWeight: 600,
  };
  switch (status) {
    case "ready":
      return { ...base, background: "#d1fae5", color: "#065f46" };
    case "processing":
      return { ...base, background: "#fef3c7", color: "#92400e" };
    case "error":
      return { ...base, background: "#fee2e2", color: "#991b1b" };
    default:
      return { ...base, background: "#f3f4f6", color: "#374151" };
  }
}

function isIgnoredResult(
  result: ImportQualityReport | { ignored: boolean; reason: string },
): result is { ignored: boolean; reason: string } {
  return "ignored" in result;
}

// ---------------------------------------------------------------------------
// Upload panel
// ---------------------------------------------------------------------------

function UploadPanel() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [year, setYear] = useState<string>("");
  const [month, setMonth] = useState<string>("");
  const [result, setResult] = useState<
    ImportQualityReport | { ignored: boolean; reason: string } | null
  >(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setResult(null);
    try {
      const res = await importApi.uploadFile(
        file,
        year ? Number(year) : undefined,
        month ? Number(month) : undefined,
      );
      setResult(res);
      void queryClient.invalidateQueries({ queryKey: ["import-files"] });
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Error al subir archivo.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div style={{ marginBottom: "24px" }}>
      <div className="feature-header" style={{ marginBottom: "12px" }}>
        <div className="feature-title">
          <Upload size={20} />
          <h2>Subir archivo</h2>
        </div>
      </div>

      <div className="audit-filters">
        <label>
          Archivo
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.xlsb,.csv,.pdf"
            style={{ display: "block", marginTop: "4px" }}
          />
        </label>
        <label>
          Año (opcional)
          <input
            type="number"
            value={year}
            onChange={e => setYear(e.target.value)}
            placeholder="2025"
            style={{ width: "90px" }}
          />
        </label>
        <label>
          Mes (opcional)
          <input
            type="number"
            value={month}
            onChange={e => setMonth(e.target.value)}
            placeholder="1–12"
            min={1}
            max={12}
            style={{ width: "70px" }}
          />
        </label>
        <button className="btn-primary" onClick={handleUpload} disabled={uploading}>
          <Upload size={15} />
          {uploading ? "Subiendo…" : "Subir"}
        </button>
      </div>

      {uploadError && <p className="error-text">{uploadError}</p>}

      {result && isIgnoredResult(result) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "#fef3c7",
            color: "#92400e",
            padding: "10px 14px",
            borderRadius: "6px",
            marginTop: "12px",
          }}
        >
          <AlertTriangle size={16} />
          <span>Archivo ignorado: {result.reason}</span>
        </div>
      )}

      {result && !isIgnoredResult(result) && (
        <div
          style={{
            background: "#f0fdf4",
            border: "1px solid #86efac",
            borderRadius: "8px",
            padding: "14px 18px",
            marginTop: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
            <CheckCircle size={16} color="#16a34a" />
            <strong style={{ color: "#15803d" }}>Archivo procesado: {result.file_name}</strong>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "8px" }}>
            {[
              { label: "Total staged", value: result.total_staged },
              { label: "Coincidencias exactas", value: result.exact_matches },
              { label: "Pendiente revisión", value: result.pending_review },
              { label: "Conflictos", value: result.conflicts },
            ].map(stat => (
              <div
                key={stat.label}
                style={{
                  background: "#fff",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  border: "1px solid #d1fae5",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>{stat.label}</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#111827" }}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Staged records panel
// ---------------------------------------------------------------------------

function StagedPanel({ fileId }: { fileId: string }) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["import-staged", fileId],
    queryFn: () => importApi.listStaged({ source_file_id: fileId, limit: 200 }),
  });

  const reviewMutation = useMutation({
    mutationFn: ({ recordId, action }: { recordId: string; action: string }) =>
      importApi.reviewRecord(recordId, action),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["import-staged", fileId] });
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => importApi.applyApproved(fileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["import-staged", fileId] });
      void queryClient.invalidateQueries({ queryKey: ["import-files"] });
    },
  });

  return (
    <div style={{ marginTop: "24px" }}>
      <div className="feature-header" style={{ marginBottom: "12px" }}>
        <div className="feature-title">
          <h3 style={{ margin: 0 }}>Registros staged</h3>
          {data && <span className="count-badge">{data.total}</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {applyMutation.isSuccess && (
            <span style={{ fontSize: "0.85rem", color: "#374151" }}>
              Aplicados: {applyMutation.data.applied} / Omitidos: {applyMutation.data.skipped}
            </span>
          )}
          <button
            className="btn-primary"
            onClick={() => applyMutation.mutate()}
            disabled={applyMutation.isPending}
          >
            <CheckCircle size={15} />
            {applyMutation.isPending ? "Aplicando…" : "Aplicar Aprobados"}
          </button>
        </div>
      </div>

      {applyMutation.isError && (
        <p className="error-text">Error al aplicar registros aprobados.</p>
      )}

      {isLoading && <p className="loading-text">Cargando registros…</p>}
      {error && <p className="error-text">Error al cargar registros staged.</p>}

      {data && data.items.length === 0 && (
        <p className="empty-text">No hay registros staged para este archivo.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Valor raw</th>
                <th>Confianza</th>
                <th>Match status</th>
                <th>Revisión</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((rec: ImportStagedRecord) => (
                <tr key={rec.id}>
                  <td>{rec.record_type}</td>
                  <td className="cell-detail">
                    <span className="snapshot-hint">
                      {rec.raw_value ?? "—"}
                    </span>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {rec.confidence !== null ? `${Math.round(rec.confidence * 100)}%` : "—"}
                  </td>
                  <td>{rec.match_status ?? "—"}</td>
                  <td>
                    <span style={reviewBadgeStyle(rec.review_status)}>
                      {rec.review_status}
                    </span>
                  </td>
                  <td>
                    {rec.review_status === "pending" && (
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-primary"
                          style={{ padding: "3px 10px", fontSize: "0.8rem" }}
                          disabled={reviewMutation.isPending}
                          onClick={() =>
                            reviewMutation.mutate({ recordId: rec.id, action: "approve" })
                          }
                        >
                          Aprobar
                        </button>
                        <button
                          className="btn-ghost"
                          style={{
                            padding: "3px 10px",
                            fontSize: "0.8rem",
                            color: "#991b1b",
                            borderColor: "#fca5a5",
                          }}
                          disabled={reviewMutation.isPending}
                          onClick={() =>
                            reviewMutation.mutate({ recordId: rec.id, action: "reject" })
                          }
                        >
                          <XCircle size={13} /> Rechazar
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ImportView() {
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["import-files"],
    queryFn: () => importApi.listFiles(),
  });

  return (
    <div className="feature-panel">
      <UploadPanel />

      <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "8px 0 20px" }} />

      <div className="feature-header" style={{ marginBottom: "12px" }}>
        <div className="feature-title">
          <h2>Archivos importados</h2>
          {data && <span className="count-badge">{data.total}</span>}
        </div>
      </div>

      {isLoading && <p className="loading-text">Cargando archivos…</p>}
      {error && <p className="error-text">Error al cargar archivos importados.</p>}

      {data && data.items.length === 0 && (
        <p className="empty-text">No hay archivos importados aún.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>Registros</th>
                <th>Periodo</th>
                <th>Importado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((f: ImportSourceFile) => (
                <tr key={f.id}>
                  <td>{f.file_name}</td>
                  <td>{f.file_type}</td>
                  <td>
                    <span style={statusBadgeStyle(f.status)}>{f.status}</span>
                  </td>
                  <td style={{ textAlign: "center" }}>{f.record_count}</td>
                  <td>
                    {f.detected_period_year && f.detected_period_month
                      ? `${f.detected_period_year}-${String(f.detected_period_month).padStart(2, "0")}`
                      : "—"}
                  </td>
                  <td className="cell-date">{formatDate(f.imported_at)}</td>
                  <td>
                    <button
                      className="btn-ghost"
                      style={{ padding: "3px 10px", fontSize: "0.8rem" }}
                      onClick={() =>
                        setSelectedFileId(prev => (prev === f.id ? null : f.id))
                      }
                    >
                      {selectedFileId === f.id ? "Ocultar" : "Ver staged"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedFileId && <StagedPanel fileId={selectedFileId} />}
    </div>
  );
}
