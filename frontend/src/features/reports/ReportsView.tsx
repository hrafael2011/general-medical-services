import { BarChart2, Download, Search } from "lucide-react";
import { useState } from "react";
import { reportsApi, OperationalSummary, NotificationsSummary } from "../../api/reports";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ReportsView() {
  const now = new Date();
  const [year, setYear] = useState<number>(now.getFullYear());
  const [month, setMonth] = useState<number>(now.getMonth() + 1);

  // Section 1 — Excel download
  const [downloadingHistory, setDownloadingHistory] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Section 2 — Operational summary
  const [opLoading, setOpLoading] = useState(false);
  const [opError, setOpError] = useState<string | null>(null);
  const [opSummary, setOpSummary] = useState<OperationalSummary | null>(null);

  // Section 3 — Notifications summary
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifError, setNotifError] = useState<string | null>(null);
  const [notifSummary, setNotifSummary] = useState<NotificationsSummary | null>(null);

  async function handleDownloadHistory() {
    setDownloadingHistory(true);
    setDownloadError(null);
    try {
      const blob = await reportsApi.downloadDoctorHistoryExcel(year, month);
      triggerBlobDownload(blob, `historial_medicos_${year}_${String(month).padStart(2, "0")}.xlsx`);
    } catch (err: unknown) {
      setDownloadError(err instanceof Error ? err.message : "Error al descargar.");
    } finally {
      setDownloadingHistory(false);
    }
  }

  async function handleOperationalSummary() {
    setOpLoading(true);
    setOpError(null);
    setOpSummary(null);
    try {
      const data = await reportsApi.getOperationalSummary(year, month);
      setOpSummary(data);
    } catch (err: unknown) {
      setOpError(err instanceof Error ? err.message : "Error al obtener resumen operacional.");
    } finally {
      setOpLoading(false);
    }
  }

  async function handleNotifSummary() {
    setNotifLoading(true);
    setNotifError(null);
    setNotifSummary(null);
    try {
      const data = await reportsApi.getNotificationsSummary(year, month);
      setNotifSummary(data);
    } catch (err: unknown) {
      setNotifError(err instanceof Error ? err.message : "Error al obtener resumen de notificaciones.");
    } finally {
      setNotifLoading(false);
    }
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <BarChart2 size={20} />
          <h2>Reportes</h2>
        </div>
      </div>

      {/* Period picker — shared */}
      <div className="audit-filters" style={{ marginBottom: "24px" }}>
        <label>
          Año
          <input
            type="number"
            value={year}
            onChange={e => setYear(Number(e.target.value))}
            style={{ width: "90px" }}
          />
        </label>
        <label>
          Mes
          <input
            type="number"
            value={month}
            onChange={e => setMonth(Number(e.target.value))}
            min={1}
            max={12}
            style={{ width: "70px" }}
          />
        </label>
      </div>

      {/* Section 1 — Excel Downloads */}
      <section style={{ marginBottom: "28px" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "10px", color: "#374151" }}>
          Descargas Excel
        </h3>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <button
            className="btn-primary"
            onClick={handleDownloadHistory}
            disabled={downloadingHistory}
          >
            <Download size={15} />
            {downloadingHistory ? "Descargando…" : "Descargar Historial Médicos"}
          </button>
        </div>
        {downloadError && <p className="error-text">{downloadError}</p>}
      </section>

      {/* Section 2 — Operational Summary */}
      <section style={{ marginBottom: "28px" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "10px", color: "#374151" }}>
          Resumen Operacional
        </h3>
        <button
          className="btn-primary"
          onClick={handleOperationalSummary}
          disabled={opLoading}
        >
          <Search size={15} />
          {opLoading ? "Cargando…" : "Ver Resumen Operacional"}
        </button>

        {opError && <p className="error-text">{opError}</p>}

        {opSummary && (
          <div
            style={{
              marginTop: "14px",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
              padding: "16px 20px",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
              gap: "12px",
            }}
          >
            {[
              { label: "Médicos activos", value: opSummary.active_doctors },
              { label: "Estado calendario", value: opSummary.calendar_status ?? "—" },
              { label: "Total asignaciones", value: opSummary.total_assignments },
              { label: "Brechas sin resolver", value: opSummary.unresolved_gaps },
            ].map(stat => (
              <div
                key={stat.label}
                style={{
                  background: "#fff",
                  borderRadius: "6px",
                  padding: "10px 14px",
                  border: "1px solid #e5e7eb",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>{stat.label}</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#111827", marginTop: "4px" }}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Section 3 — Notifications Summary */}
      <section>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "10px", color: "#374151" }}>
          Resumen Notificaciones
        </h3>
        <button
          className="btn-primary"
          onClick={handleNotifSummary}
          disabled={notifLoading}
        >
          <Search size={15} />
          {notifLoading ? "Cargando…" : "Ver Resumen Notificaciones"}
        </button>

        {notifError && <p className="error-text">{notifError}</p>}

        {notifSummary && (
          <div
            style={{
              marginTop: "14px",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
              padding: "16px 20px",
            }}
          >
            <div style={{ marginBottom: "12px" }}>
              <span style={{ fontSize: "0.85rem", color: "#6b7280" }}>Total: </span>
              <strong>{notifSummary.total}</strong>
            </div>

            <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
              <div>
                <p style={{ fontSize: "0.8rem", fontWeight: 600, color: "#374151", marginBottom: "6px" }}>
                  Por estado
                </p>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.85rem" }}>
                  {Object.entries(notifSummary.by_status).map(([k, v]) => (
                    <li key={k} style={{ marginBottom: "4px", color: "#4b5563" }}>
                      <span style={{ fontWeight: 500 }}>{k}:</span> {v}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <p style={{ fontSize: "0.8rem", fontWeight: 600, color: "#374151", marginBottom: "6px" }}>
                  Por tipo
                </p>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.85rem" }}>
                  {Object.entries(notifSummary.by_type).map(([k, v]) => (
                    <li key={k} style={{ marginBottom: "4px", color: "#4b5563" }}>
                      <span style={{ fontWeight: 500 }}>{k}:</span> {v}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
