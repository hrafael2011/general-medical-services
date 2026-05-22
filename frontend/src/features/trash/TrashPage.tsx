import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, RotateCcw } from "lucide-react";
import { trashApi, TrashItem } from "../../api/trash";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";

const TABS = [
  { key: "doctors", label: "Doctores" },
  { key: "users", label: "Usuarios" },
  { key: "ranks", label: "Rangos" },
  { key: "departments", label: "Departamentos" },
] as const;

const TYPE_LABELS: Record<string, string> = {
  doctors: "doctores",
  users: "usuarios",
  ranks: "rangos",
  departments: "departamentos",
};

export function TrashPage() {
  const [activeTab, setActiveTab] = useState<string>("doctors");
  const [confirmDelete, setConfirmDelete] = useState<{ type: string; id: string; name: string } | null>(null);
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["trash", activeTab],
    queryFn: () => trashApi.list(activeTab),
  });

  const restoreMutation = useMutation({
    mutationFn: ({ type, id }: { type: string; id: string }) =>
      trashApi.restore(type, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trash", activeTab] });
      addToast("success", "Elemento restaurado correctamente");
    },
    onError: () => addToast("error", "Error al restaurar el elemento"),
  });

  const hardDeleteMutation = useMutation({
    mutationFn: ({ type, id }: { type: string; id: string }) =>
      trashApi.hardDelete(type, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trash", activeTab] });
      addToast("success", "Elemento eliminado permanentemente");
      setConfirmDelete(null);
    },
    onError: () => addToast("error", "Error al eliminar el elemento"),
  });

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <Trash2 size={20} />
          <h2>Papelera</h2>
        </div>
      </div>

      <p className="subtitle">
        Elementos eliminados — restauración y eliminación permanente
      </p>

      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #e5e7eb", marginBottom: 20 }}>
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            className={activeTab === key ? "btn-primary" : "btn-ghost"}
            style={{
              padding: "8px 16px",
              borderRadius: "6px 6px 0 0",
              border: "none",
              fontSize: 13,
            }}
            onClick={() => setActiveTab(key)}
          >
            {label} ({items.length})
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="loading-text">Cargando...</p>
      ) : items.length === 0 ? (
        <p className="empty-state">
          No hay {TYPE_LABELS[activeTab]} eliminados.
        </p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Eliminado el</th>
                <th />
                <th style={{ textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item: TrashItem) => (
                <tr key={item.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{item.name}</div>
                    {item.email && <div style={{ color: "#9ca3af", fontSize: 11 }}>{item.email}</div>}
                  </td>
                  <td style={{ color: "#6b7280" }}>
                    {item.deleted_at ? new Date(item.deleted_at).toLocaleDateString() : "-"}
                  </td>
                  <td style={{ color: "#6b7280" }}>
                    {activeTab === "ranks"
                      ? item.abbreviation
                      : activeTab === "departments"
                        ? item.normalized_name
                        : item.role || item.rank_name || ""}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn-outline"
                      style={{ color: "#059669", borderColor: "#10b981", marginRight: 6 }}
                      onClick={() => restoreMutation.mutate({ type: activeTab, id: item.id })}
                      disabled={restoreMutation.isPending}
                    >
                      <RotateCcw size={13} /> Restaurar
                    </button>
                    <button
                      className="btn-outline"
                      style={{ color: "#dc2626", borderColor: "#ef4444" }}
                      onClick={() => setConfirmDelete({ type: activeTab, id: item.id, name: item.name })}
                    >
                      <Trash2 size={13} /> Eliminar def.
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Confirmar eliminación permanente"
        message={`"${confirmDelete?.name}" se perderá para siempre. Esta acción no se puede deshacer.`}
        confirmLabel="Sí, eliminar"
        variant="danger"
        onConfirm={() => {
          if (confirmDelete) hardDeleteMutation.mutate({ type: confirmDelete.type, id: confirmDelete.id });
        }}
        onCancel={() => setConfirmDelete(null)}
        isLoading={hardDeleteMutation.isPending}
      />
    </div>
  );
}
