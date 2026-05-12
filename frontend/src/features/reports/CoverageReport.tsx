import { useState } from "react";
import { useToast } from "../../components/Toast";
import { ReportFilters, FilterLabel, ActionButtons } from "../../components/ReportFilters";
import { ReportSummaryCards } from "../../components/ReportSummaryCards";
import { reportsApi, CoverageResponse } from "../../api/reports";

export function CoverageReport() {
  const { addToast } = useToast();
  const now = new Date();
  const [ys, setYs] = useState(now.getFullYear());
  const [ms, setMs] = useState(now.getMonth() + 1);
  const [ye, setYe] = useState(now.getFullYear());
  const [me, setMe] = useState(now.getMonth() + 1);
  const [area, setArea] = useState("");
  const [data, setData] = useState<CoverageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedArea, setExpandedArea] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setData(null);
    try {
      const res = await reportsApi.getCoverage({
        year_start: ys, month_start: ms,
        year_end: ye, month_end: me,
        area: area || undefined,
      });
      setData(res);
    } catch {
      addToast("error", "Error al cargar reporte de cobertura.");
    } finally {
      setLoading(false);
    }
  }

  async function exportPdf() {
    try {
      const blob = await reportsApi.getCoveragePdf({
        year_start: ys, month_start: ms,
        year_end: ye, month_end: me,
        area: area || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cobertura_${ys}_${ms}.pdf`;
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
        <FilterLabel label="Desde mes/año">
          <div style={{ display: "flex", gap: "4px" }}>
            <input type="number" value={ms} onChange={e => setMs(Number(e.target.value))} min={1} max={12} style={{ width: "60px" }} />
            <input type="number" value={ys} onChange={e => setYs(Number(e.target.value))} style={{ width: "70px" }} />
          </div>
        </FilterLabel>
        <FilterLabel label="Hasta mes/año">
          <div style={{ display: "flex", gap: "4px" }}>
            <input type="number" value={me} onChange={e => setMe(Number(e.target.value))} min={1} max={12} style={{ width: "60px" }} />
            <input type="number" value={ye} onChange={e => setYe(Number(e.target.value))} style={{ width: "70px" }} />
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
        <ActionButtons onSearch={load} onPdf={exportPdf} loading={loading} />
      </ReportFilters>

      {data && (
        <>
          <ReportSummaryCards cards={[
            { label: "% Cobertura General", value: `${data.overall_coverage_pct}%` },
            { label: "Total Brechas", value: data.total_gaps },
            { label: "Área Más Crítica", value: data.most_critical_area ?? "—" },
            { label: "Día Más Débil", value: data.weakest_day ?? "—" },
          ]} />

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Área</th>
                  <th>Días Cubiertos</th>
                  <th>Días Descubiertos</th>
                  <th>% Cobertura</th>
                </tr>
              </thead>
              <tbody>
                {data.by_area.map(area => (
                  <tr
                    key={area.area_id}
                    onClick={() => setExpandedArea(expandedArea === area.area_id ? null : area.area_id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td><strong>{area.area_name}</strong></td>
                    <td style={{ textAlign: "center" }}>{area.days_covered}</td>
                    <td style={{ textAlign: "center", color: area.days_uncovered > 0 ? "#dc2626" : "inherit" }}>
                      {area.days_uncovered}
                    </td>
                    <td style={{ textAlign: "center" }}>{area.coverage_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {expandedArea && (
            <div style={{ marginTop: "12px" }}>
              {data.by_area
                .filter(a => a.area_id === expandedArea)
                .map(a => (
                  <div key={a.area_id} style={{ padding: "8px 20px", background: "#f9fafb", borderRadius: "8px" }}>
                    <strong style={{ fontSize: "0.8rem" }}>Brechas ({a.gaps.length}):</strong>
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                      {a.gaps.slice(0, 50).map(g => (
                        <span key={g.date} style={{
                          background: "#fee2e2", color: "#991b1b", padding: "2px 8px",
                          borderRadius: "4px", fontSize: "0.75rem"
                        }}>
                          {g.date} ({g.day_name})
                        </span>
                      ))}
                      {a.gaps.length > 50 && (
                        <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                          ... y {a.gaps.length - 50} más
                        </span>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </>
      )}

      {loading && <p className="loading-text">Cargando reporte de cobertura…</p>}
    </div>
  );
}
