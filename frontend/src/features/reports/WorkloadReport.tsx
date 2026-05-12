import { useState } from "react";
import { useToast } from "../../components/Toast";
import { ReportFilters, FilterLabel, ActionButtons } from "../../components/ReportFilters";
import { ReportSummaryCards } from "../../components/ReportSummaryCards";
import { reportsApi, WorkloadResponse } from "../../api/reports";

export function WorkloadReport() {
  const { addToast } = useToast();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [area, setArea] = useState("");
  const [groupBy, setGroupBy] = useState("none");
  const [data, setData] = useState<WorkloadResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedDoctor, setExpandedDoctor] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setData(null);
    try {
      const res = await reportsApi.getWorkload({
        year, month,
        area: area || undefined,
        group_by: groupBy,
      });
      setData(res);
    } catch {
      addToast("error", "Error al cargar reporte de carga de trabajo.");
    } finally {
      setLoading(false);
    }
  }

  async function exportPdf() {
    try {
      const blob = await reportsApi.getWorkloadPdf({
        year, month,
        area: area || undefined,
        group_by: groupBy,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `carga_trabajo_${year}_${month}.pdf`;
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
        <FilterLabel label="Mes/Año">
          <div style={{ display: "flex", gap: "4px" }}>
            <input type="number" value={month} onChange={e => setMonth(Number(e.target.value))} min={1} max={12} style={{ width: "60px" }} />
            <input type="number" value={year} onChange={e => setYear(Number(e.target.value))} style={{ width: "70px" }} />
          </div>
        </FilterLabel>
        <FilterLabel label="Área">
          <select value={area} onChange={e => setArea(e.target.value)} style={{ width: "130px" }}>
            <option value="">Todas</option>
            <option value="emergencia">Emergencia</option>
            <option value="pista">Pista</option>
            <option value="disponible">Disponible</option>
          </select>
        </FilterLabel>
        <FilterLabel label="Agrupar por">
          <select value={groupBy} onChange={e => setGroupBy(e.target.value)} style={{ width: "130px" }}>
            <option value="none">Sin agrupar</option>
            <option value="area">Área</option>
            <option value="rank">Rango</option>
            <option value="department">Departamento</option>
          </select>
        </FilterLabel>
        <ActionButtons onSearch={load} onPdf={exportPdf} loading={loading} />
      </ReportFilters>

      {data && (
        <>
          <ReportSummaryCards cards={[
            { label: "Total Servicios", value: data.total_services },
            { label: "Médicos Activos", value: data.active_doctors },
            { label: "Promedio por Médico", value: data.avg_per_doctor },
            { label: "Mayor Carga", value: data.most_load ? `${data.most_load.name} (${data.most_load.total})` : "—" },
            { label: "Menor Carga", value: data.least_load ? `${data.least_load.name} (${data.least_load.total})` : "—" },
          ]} />

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Médico</th>
                  <th>Rango</th>
                  <th>Sexo</th>
                  <th>Depto</th>
                  <th>Emerg.</th>
                  <th>Pista</th>
                  <th>Disp.</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map(entry => (
                  <tr
                    key={entry.doctor_id}
                    onClick={() => setExpandedDoctor(expandedDoctor === entry.doctor_id ? null : entry.doctor_id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{entry.name}</td>
                    <td>{entry.rank ?? "—"}</td>
                    <td>{entry.sex ?? "—"}</td>
                    <td>{entry.department ?? "—"}</td>
                    <td style={{ textAlign: "center" }}>{entry.emergencia}</td>
                    <td style={{ textAlign: "center" }}>{entry.pista}</td>
                    <td style={{ textAlign: "center" }}>{entry.disponible}</td>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>{entry.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {expandedDoctor && (
            <div style={{ marginTop: "12px" }}>
              {data.entries
                .filter(e => e.doctor_id === expandedDoctor)
                .map(e => (
                  <div key={e.doctor_id} style={{ padding: "8px 20px", background: "#f9fafb", borderRadius: "8px" }}>
                    <strong style={{ fontSize: "0.8rem" }}>Detalle:</strong>
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                      {e.details.map(d => (
                        <span key={d.date} style={{
                          background: "#e0e7ff", color: "#3730a3", padding: "2px 8px",
                          borderRadius: "4px", fontSize: "0.75rem"
                        }}>
                          {d.date} - {d.area}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </>
      )}

      {loading && <p className="loading-text">Cargando reporte de carga de trabajo…</p>}
    </div>
  );
}
