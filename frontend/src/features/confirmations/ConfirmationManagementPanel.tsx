import { CheckCircle, Search, RotateCw } from "lucide-react";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { confirmationsApi, ConfirmationRequestRead } from "../../api/confirmations";
import { useToast } from "../../components/Toast";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  confirmed: "Confirmado",
  expired: "Vencido",
  cancelled: "Cancelado",
  received: "Recibido",
};

const TYPE_LABELS: Record<string, string> = {
  service: "Servicio",
  mission: "Misión",
};

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-DO", { dateStyle: "short", timeStyle: "short" });
}

function statusBadgeStyle(status: string): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 8px", borderRadius: "4px", fontSize: "0.78rem", fontWeight: 600,
  };
  const map: Record<string, React.CSSProperties> = {
    pending: { ...base, background: "#fef3c7", color: "#92400e" },
    confirmed: { ...base, background: "#d1fae5", color: "#065f46" },
    expired: { ...base, background: "#fee2e2", color: "#991b1b" },
    cancelled: { ...base, background: "#f3f4f6", color: "#6b7280" },
    received: { ...base, background: "#e0f2fe", color: "#075985" },
  };
  return map[status] ?? { ...base, background: "#f3f4f6", color: "#374151" };
}

export function ConfirmationManagementPanel() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [statusFilter, setStatusFilter] = useState("");
  const [appliedStatus, setAppliedStatus] = useState("");

  function applyFilters() {
    setAppliedStatus(statusFilter);
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ["confirmations", appliedStatus],
    queryFn: () => confirmationsApi.list(appliedStatus ? { status: appliedStatus } : undefined),
  });

  const processMutation = useMutation({
    mutationFn: () => confirmationsApi.processOverdue(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["confirmations"] });
      addToast("success", `Procesadas: ${result.expired} vencidas.`);
    },
    onError: () => addToast("error", "Error al procesar confirmaciones vencidas."),
  });

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <CheckCircle size={20} />
          <h2>Gestión de Confirmaciones</h2>
          {data && <span className="count-badge">{data.total}</span>}
        </div>
        <button
          className="btn-primary"
          onClick={() => processMutation.mutate()}
          disabled={processMutation.isPending}
        >
          <RotateCw size={15} />
          {processMutation.isPending ? "Procesando…" : "Procesar vencidas"}
        </button>
      </div>

      <div className="audit-filters">
        <label>
          Estado
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">Todos</option>
            <option value="pending">Pendiente</option>
            <option value="confirmed">Confirmado</option>
            <option value="expired">Vencido</option>
            <option value="cancelled">Cancelado</option>
          </select>
        </label>
        <button className="btn-primary" onClick={applyFilters}>
          <Search size={15} /> Filtrar
        </button>
      </div>

      {isLoading && <p className="loading-text">Cargando confirmaciones…</p>}
      {error && <p className="error-text">Error al cargar confirmaciones.</p>}

      {data && data.items.length === 0 && (
        <p className="empty-text">No hay confirmaciones registradas.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Médico</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>Canal</th>
                <th>Creado</th>
                <th>Respondido</th>
                <th>Escalado</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(item => (
                <tr key={item.id}>
                  <td>{item.doctor_name ?? item.doctor_id.slice(0, 8) + "…"}</td>
                  <td>{TYPE_LABELS[item.confirmation_type] ?? item.confirmation_type}</td>
                  <td><span style={statusBadgeStyle(item.status)}>{STATUS_LABELS[item.status] ?? item.status}</span></td>
                  <td>{item.response_channel ?? "—"}</td>
                  <td className="cell-date">{formatDate(item.created_at)}</td>
                  <td className="cell-date">{formatDate(item.responded_at)}</td>
                  <td className="cell-date">{formatDate(item.escalated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
