import { ClipboardList, Search } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi, AuditEventRead, AuditFilters } from "../../api/audit";

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
  calendar_created: "Calendario creado",
  calendar_approved: "Calendario aprobado",
  calendar_new_version: "Nueva versión de calendario",
  calendar_deleted: "Calendario eliminado",
  assignment_added: "Servicio asignado",
  assignment_removed: "Servicio eliminado",
  assignment_replaced: "Servicio reemplazado",
  mission_ranking_generated: "Ranking de misiones",
  mission_confirmed: "Misión confirmada",
};

const ENTITY_LABELS: Record<string, string> = {
  doctor: "Médico",
  user: "Usuario",
  availability: "Disponibilidad",
  restriction: "Restricción",
  calendar: "Calendario",
  assignment: "Asignación",
  mission: "Misión",
  mission_ranking: "Ranking de misiones",
};

const FIELD_LABELS: Record<string, string> = {
  name: "Nombre",
  sex: "Sexo",
  rank_id: "Rango",
  department_id: "Departamento",
  notes: "Notas",
  active: "Activo en sistema",
  service_active: "Activo para servicio",
  participa_misiones: "Misiones",
  whatsapp_phone: "WhatsApp",
  service_inactive_reason_id: "Motivo de inactividad",
  service_inactive_detail: "Detalle de inactividad",
  doctor_id: "Médico",
  service_date: "Fecha de servicio",
  service_area_id: "Área",
  mission_date: "Fecha de misión",
  status: "Estado",
  version_number: "Versión",
};

function shortId(value: string | null | undefined) {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function snapshotText(snapshot: Record<string, unknown> | null | undefined) {
  if (!snapshot) return "Sin datos adicionales";
  const entries = Object.entries(snapshot).slice(0, 6);
  if (entries.length === 0) return "Sin datos adicionales";
  return entries
    .map(([key, value]) => `${FIELD_LABELS[key] ?? key}: ${formatValue(value)}`)
    .join(" · ");
}

function formatValue(value: unknown) {
  if (value === true) return "Sí";
  if (value === false) return "No";
  if (value === null || value === undefined || value === "") return "Sin especificar";
  if (value === "male") return "Masculino";
  if (value === "female") return "Femenino";
  if (Array.isArray(value)) return `${value.length} elementos`;
  if (typeof value === "object") return "Datos estructurados";
  return String(value);
}

function fallbackEntity(event: AuditEventRead) {
  const label = ENTITY_LABELS[event.entity_type] ?? event.entity_type;
  const name = event.after_snapshot?.name ?? event.before_snapshot?.name;
  return typeof name === "string" ? `${label}: ${name}` : label;
}

function fallbackSummary(event: AuditEventRead) {
  if (event.after_snapshot) return snapshotText(event.after_snapshot);
  if (event.before_snapshot) return snapshotText(event.before_snapshot);
  if (event.metadata_) return snapshotText(event.metadata_);
  return "Evento registrado en auditoría.";
}

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
                <th>Entidad afectada</th>
                <th>Realizado por</th>
                <th>Resumen</th>
                <th>Detalles técnicos</th>
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
                  <td className="cell-entity">{event.entity_display ?? fallbackEntity(event)}</td>
                  <td className="cell-actor">{event.actor_display ?? (event.actor_id ? "Usuario del sistema" : "Sistema")}</td>
                  <td className="cell-detail">{event.detail_summary ?? fallbackSummary(event)}</td>
                  <td className="cell-detail">
                    <details className="audit-technical-details">
                      <summary>Ver</summary>
                      <div>ID entidad: <span className="cell-id">{shortId(event.entity_id)}</span></div>
                      <div>ID actor: <span className="cell-id">{shortId(event.actor_id)}</span></div>
                      {event.request_id && <div>Solicitud: <span className="cell-id">{shortId(event.request_id)}</span></div>}
                      <div>{snapshotText(event.after_snapshot ?? event.before_snapshot ?? event.metadata_)}</div>
                    </details>
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
