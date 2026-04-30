import { ClipboardList, Search } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi, AuditFilters } from "../../api/audit";

const ACTION_LABELS: Record<string, string> = {
  doctor_created: "Médico creado",
  doctor_updated: "Médico actualizado",
  doctor_service_deactivated: "Servicio desactivado",
  doctor_service_reactivated: "Servicio reactivado",
  availability_set: "Disponibilidad cargada",
  restriction_added: "Restricción añadida",
  restriction_lifted: "Restricción levantada",
  user_created: "Usuario creado",
  password_reset: "Contraseña reseteada",
  password_changed: "Contraseña cambiada",
  login_failed: "Login fallido",
};

const ENTITY_LABELS: Record<string, string> = {
  doctor: "Médico",
  user: "Usuario",
  availability: "Disponibilidad",
  restriction: "Restricción",
};

export function AuditLog() {
  const [filters, setFilters] = useState<AuditFilters>({ limit: 50, offset: 0 });
  const [actionType, setActionType] = useState("");
  const [entityType, setEntityType] = useState("");

  function applyFilters() {
    setFilters({
      action_type: actionType || undefined,
      entity_type: entityType || undefined,
      limit: 50,
      offset: 0,
    });
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ["audit", filters],
    queryFn: () => auditApi.list(filters),
  });

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString("es-DO", {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <ClipboardList size={20} />
          <h2>Auditoría</h2>
          {data && <span className="count-badge">{data.total}</span>}
        </div>
      </div>

      <div className="audit-filters">
        <label>
          Tipo de acción
          <select value={actionType} onChange={e => setActionType(e.target.value)}>
            <option value="">Todas</option>
            {Object.entries(ACTION_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
        <label>
          Entidad
          <select value={entityType} onChange={e => setEntityType(e.target.value)}>
            <option value="">Todas</option>
            {Object.entries(ENTITY_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
        <button className="btn-primary" onClick={applyFilters}>
          <Search size={15} /> Filtrar
        </button>
      </div>

      {isLoading && <p className="loading-text">Cargando eventos…</p>}
      {error && <p className="error-text">Error al cargar auditoría.</p>}

      {data && data.items.length === 0 && (
        <p className="empty-text">No hay eventos registrados.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Acción</th>
                <th>Entidad</th>
                <th>ID entidad</th>
                <th>Actor</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(event => (
                <tr key={event.id}>
                  <td className="cell-date">{formatDate(event.occurred_at)}</td>
                  <td>
                    <span className={`action-badge action-${event.action_type.split("_")[0]}`}>
                      {ACTION_LABELS[event.action_type] ?? event.action_type}
                    </span>
                  </td>
                  <td>{ENTITY_LABELS[event.entity_type] ?? event.entity_type}</td>
                  <td className="cell-id">{event.entity_id ? event.entity_id.slice(0, 8) + "…" : "—"}</td>
                  <td className="cell-id">{event.actor_id ? event.actor_id.slice(0, 8) + "…" : "Sistema"}</td>
                  <td className="cell-detail">
                    {event.after_snapshot
                      ? <span className="snapshot-hint">{Object.keys(event.after_snapshot).slice(0, 2).join(", ")}</span>
                      : "—"}
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
