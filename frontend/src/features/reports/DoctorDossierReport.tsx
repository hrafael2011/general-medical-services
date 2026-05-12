import { useState } from "react";
import { useToast } from "../../components/Toast";
import { ReportFilters, FilterLabel, ActionButtons } from "../../components/ReportFilters";
import { ReportSummaryCards } from "../../components/ReportSummaryCards";
import { reportsApi, DossierResponse } from "../../api/reports";

export function DoctorDossierReport() {
  const { addToast } = useToast();
  const [doctorId, setDoctorId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [data, setData] = useState<DossierResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!doctorId.trim()) {
      addToast("error", "Selecciona un médico.");
      return;
    }
    setLoading(true);
    setData(null);
    try {
      const res = await reportsApi.getDoctorDossier(
        doctorId,
        dateFrom || undefined,
        dateTo || undefined,
      );
      setData(res);
    } catch {
      addToast("error", "Error al cargar ficha del médico.");
    } finally {
      setLoading(false);
    }
  }

  async function exportPdf() {
    if (!doctorId.trim()) return;
    try {
      const blob = await reportsApi.getDoctorDossierPdf(
        doctorId,
        dateFrom || undefined,
        dateTo || undefined,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ficha_medico_${doctorId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      addToast("success", "PDF descargado.");
    } catch {
      addToast("error", "Error al descargar PDF.");
    }
  }

  return (
    <div>
      <ReportFilters>
        <FilterLabel label="Médico (ID)">
          <input
            type="text"
            value={doctorId}
            onChange={e => setDoctorId(e.target.value)}
            placeholder="ID del médico"
            style={{ width: "200px" }}
          />
        </FilterLabel>
        <FilterLabel label="Desde">
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={{ width: "150px" }} />
        </FilterLabel>
        <FilterLabel label="Hasta">
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} style={{ width: "150px" }} />
        </FilterLabel>
        <ActionButtons
          onSearch={load}
          onPdf={data ? exportPdf : undefined}
          loading={loading}
        />
      </ReportFilters>

      {data && (
        <>
          <ReportSummaryCards cards={[
            { label: "Médico", value: data.name },
            { label: "Rango", value: data.rank ?? "—" },
            { label: "Departamento", value: data.department ?? "—" },
            { label: "Total Servicios", value: data.total_services },
            { label: "Promedio Semanal", value: data.avg_weekly },
          ]} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div className="table-wrapper">
              <table className="data-table">
                <thead><tr><th>Área</th><th>Servicios</th></tr></thead>
                <tbody>
                  {Object.entries(data.services_by_area).map(([area, count]) => (
                    <tr key={area}><td>{area}</td><td style={{ textAlign: "center" }}>{count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead><tr><th>Misión</th><th>Estado</th></tr></thead>
                <tbody>
                  {data.missions.length === 0 && <tr><td colSpan={2} className="empty-text">Sin misiones</td></tr>}
                  {data.missions.map((m, i) => (
                    <tr key={i}><td>{m.mission}</td><td>{m.status}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {data.services.length > 0 && (
            <div className="table-wrapper" style={{ marginTop: "16px" }}>
              <table className="data-table">
                <thead><tr><th>Fecha</th><th>Día</th><th>Área</th></tr></thead>
                <tbody>
                  {data.services.map((s, i) => (
                    <tr key={i}><td>{s.date}</td><td>{s.day_name}</td><td>{s.area}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.restrictions.length > 0 && (
            <div className="table-wrapper" style={{ marginTop: "16px" }}>
              <table className="data-table">
                <thead><tr><th>Tipo</th><th>Fecha</th><th>Motivo</th></tr></thead>
                <tbody>
                  {data.restrictions.map((r, i) => (
                    <tr key={i}><td>{r.type}</td><td>{r.date ?? "—"}</td><td>{r.reason}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.availability.length > 0 && (
            <p style={{ marginTop: "12px", fontSize: "0.85rem", color: "#374151" }}>
              <strong>Disponibilidad:</strong> {data.availability.join(", ")}
            </p>
          )}
        </>
      )}

      {loading && <p className="loading-text">Cargando ficha del médico…</p>}
    </div>
  );
}
