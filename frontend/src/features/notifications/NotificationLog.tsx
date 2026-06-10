import { Bell, Search } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  notificationsApi,
  NotificationEventRead,
} from "../../api/notifications";

// ---------------------------------------------------------------------------
// Label maps
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  sent: "Enviado",
  failed: "Fallido",
  cancelled: "Cancelado",
  skipped: "Omitido",
};

const TYPE_LABELS: Record<string, string> = {
  initial_assignment: "Asignación inicial",
  reminder_12h: "Recordatorio 12h",
  mission_participant: "Misión participante",
  mission_summary: "Resumen misión",
  service_assignment_added: "Servicio agregado",
  service_assignment_removed: "Servicio removido",
  service_assignment_updated: "Servicio actualizado",
  mission_participant_added: "Participante agregado",
  mission_participant_removed: "Participante removido",
  mission_details_updated: "Misión actualizada",
  availability: "Disponibilidad",
  service_confirmed: "Servicio confirmado",
  mission_confirmed: "Misión confirmada",
};

const STATUS_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "pending", label: "Pendiente" },
  { value: "sent", label: "Enviado" },
  { value: "failed", label: "Fallido" },
  { value: "cancelled", label: "Cancelado" },
  { value: "skipped", label: "Omitido" },
];

const TYPE_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "initial_assignment", label: "Asignación inicial" },
  { value: "reminder_12h", label: "Recordatorio 12h" },
  { value: "mission_participant", label: "Misión participante" },
  { value: "mission_summary", label: "Resumen misión" },
  { value: "service_assignment_added", label: "Servicio agregado" },
  { value: "service_assignment_removed", label: "Servicio removido" },
  { value: "service_assignment_updated", label: "Servicio actualizado" },
  { value: "mission_participant_added", label: "Participante agregado" },
  { value: "mission_participant_removed", label: "Participante removido" },
  { value: "mission_details_updated", label: "Misión actualizada" },
  { value: "availability", label: "Disponibilidad" },
  { value: "service_confirmed", label: "Servicio confirmado" },
  { value: "mission_confirmed", label: "Misión confirmada" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-DO", {
    dateStyle: "short",
    timeStyle: "short",
  });
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
    case "pending":
      return { ...base, background: "#fef3c7", color: "#92400e" };
    case "sent":
      return { ...base, background: "#d1fae5", color: "#065f46" };
    case "failed":
      return { ...base, background: "#fee2e2", color: "#991b1b" };
    case "skipped":
      return { ...base, background: "#e0f2fe", color: "#075985" };
    case "cancelled":
      return { ...base, background: "#f3f4f6", color: "#6b7280" };
    default:
      return { ...base, background: "#f3f4f6", color: "#374151" };
  }
}

function messagePreview(item: NotificationEventRead): string {
  if (!item.payload) return "—";
  const msg = item.payload["message"];
  if (typeof msg !== "string" || msg.length === 0) return "—";
  return msg.length > 80 ? msg.slice(0, 80) + "…" : msg;
}

function recipient(item: NotificationEventRead): string {
  if (item.recipient_phone) return item.recipient_phone;
  if (item.recipient_doctor_id) return item.recipient_doctor_id.slice(0, 8) + "…";
  return "—";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NotificationLog() {

  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [appliedStatus, setAppliedStatus] = useState("");
  const [appliedType, setAppliedType] = useState("");

  function applyFilters() {
    setAppliedStatus(statusFilter);
    setAppliedType(typeFilter);
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ["notifications", appliedStatus, appliedType],
    queryFn: () =>
      notificationsApi.list(
        appliedStatus || undefined,
        appliedType || undefined,
      ),
  });

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <Bell size={20} />
          <h2>Notificaciones</h2>
          {data && <span className="count-badge">{data.total}</span>}
        </div>
      </div>

      <div className="audit-filters">
        <label>
          Estado
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            {STATUS_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label>
          Tipo
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            {TYPE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <button className="btn-primary" onClick={applyFilters}>
          <Search size={15} /> Filtrar
        </button>
      </div>

      {isLoading && <p className="loading-text">Cargando notificaciones…</p>}
      {error && <p className="error-text">Error al cargar notificaciones.</p>}

      {data && data.items.length === 0 && (
        <p className="empty-text">No hay notificaciones registradas.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Destinatario</th>
                <th>Provider</th>
                <th>Estado</th>
                <th>Reintentos</th>
                <th>Error</th>
                <th>Fecha</th>
                <th>Vista previa</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(item => (
                <tr key={item.id}>
                  <td>
                    {TYPE_LABELS[item.notification_type] ?? item.notification_type}
                  </td>
                  <td className="cell-id">{recipient(item)}</td>
                  <td style={{ fontSize: "0.75rem", fontFamily: "monospace" }}>
                    {item.provider || "—"}
                  </td>
                  <td>
                    <span style={statusBadgeStyle(item.status)}>
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </td>
                  <td style={{ textAlign: "center" }}>{item.retry_count}</td>
                  <td style={{ fontSize: "0.75rem", maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {item.error_message ? (
                      <span title={item.error_message} style={{ color: "#991b1b" }}>
                        {item.error_message.slice(0, 50)}{item.error_message.length > 50 ? "…" : ""}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="cell-date">{formatDate(item.created_at)}</td>
                  <td className="cell-detail">
                    <span className="snapshot-hint">{messagePreview(item)}</span>
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
