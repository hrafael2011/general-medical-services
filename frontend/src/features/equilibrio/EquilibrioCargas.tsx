import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Scale } from "lucide-react";
import { calendarsApi } from "../../api/calendars";

const MONTH_NAMES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

export function EquilibrioCargas() {
  const [selectedCalendarId, setSelectedCalendarId] = useState<string>("");

  const { data: calendars, isLoading: loadingCalendars } = useQuery({
    queryKey: ["calendars-list"],
    queryFn: calendarsApi.list,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["equilibrio", selectedCalendarId],
    queryFn: () => calendarsApi.getEquilibrio(selectedCalendarId),
    enabled: !!selectedCalendarId,
  });

  const currentCalendar = calendars?.find(c => c.id === selectedCalendarId);

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <Scale size={20} />
          <h2>Equilibrio de Cargas</h2>
        </div>
      </div>

      <div className="audit-filters">
        <label>
          Calendario
          <select
            value={selectedCalendarId}
            onChange={e => setSelectedCalendarId(e.target.value)}
          >
            <option value="">Seleccionar mes...</option>
            {calendars?.map(cal => (
              <option key={cal.id} value={cal.id}>
                {MONTH_NAMES[cal.month - 1]} {cal.year}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loadingCalendars && <p className="loading-text">Cargando calendarios…</p>}

      {!selectedCalendarId && !loadingCalendars && (
        <p className="empty-text">Seleccioná un mes para ver el equilibrio de cargas.</p>
      )}

      {isLoading && <p className="loading-text">Cargando resumen de orden de servicios…</p>}
      {error && <p className="error-text">Error al cargar datos de equilibrio.</p>}

      {data && data.items.length === 0 && (
        <p className="empty-text">
          <CheckCircle2 size={16} style={{ verticalAlign: "middle", marginRight: 4, color: "#166534" }} />
          Todos los médicos siguen el orden de servicios esperado este mes.
        </p>
      )}

      {data && data.items.length > 0 && (
        <>
          <p style={{ margin: "12px 0", color: "#475569", fontSize: "0.85rem" }}>
            Resumen de servicios por médico — {currentCalendar ? `${MONTH_NAMES[currentCalendar.month - 1]} ${currentCalendar.year}` : ""}
          </p>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Médico</th>
                  <th>Servicios asignados</th>
                  <th>Servicios esperados</th>
                  <th>Alteraciones al orden</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map(item => (
                  <tr key={item.doctor_id} className={item.alteraciones_al_orden > 0 ? "row-alterado" : "row-ok"}>
                    <td>{item.nombre_medico}</td>
                    <td>{item.servicios_asignados}</td>
                    <td>{item.servicios_esperados}</td>
                    <td>
                      {item.alteraciones_al_orden > 0 ? (
                        <span className="order-altera" style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                          <AlertTriangle size={14} /> {item.alteraciones_al_orden}
                        </span>
                      ) : (
                        <span className="order-respeta" style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                          <CheckCircle2 size={14} /> 0
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
