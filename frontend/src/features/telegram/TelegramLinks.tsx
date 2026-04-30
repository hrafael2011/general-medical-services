import { MessageCircle, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  telegramApi,
  TelegramUserLinkRead,
  CreateTelegramLinkRequest,
} from "../../api/telegram";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-DO", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function activeBadgeStyle(active: boolean): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "0.78rem",
    fontWeight: 600,
  };
  return active
    ? { ...base, background: "#d1fae5", color: "#065f46" }
    : { ...base, background: "#fee2e2", color: "#991b1b" };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TelegramLinks() {
  const queryClient = useQueryClient();

  const [telegramUserId, setTelegramUserId] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [userId, setUserId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["telegram-links"],
    queryFn: () => telegramApi.listLinks(),
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateTelegramLinkRequest) =>
      telegramApi.createLink(payload),
    onSuccess: () => {
      setTelegramUserId("");
      setTelegramUsername("");
      setUserId("");
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: ["telegram-links"] });
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => telegramApi.deleteLink(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["telegram-links"] });
    },
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!telegramUserId.trim() || !userId.trim()) {
      setFormError("Los campos Telegram User ID y User ID son obligatorios.");
      return;
    }
    setFormError(null);
    createMutation.mutate({
      telegram_user_id: telegramUserId.trim(),
      telegram_username: telegramUsername.trim() || null,
      user_id: userId.trim(),
    });
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <MessageCircle size={20} />
          <h2>Telegram — Vinculos de usuario</h2>
          {data && <span className="count-badge">{data.total}</span>}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Add link form                                                        */}
      {/* ------------------------------------------------------------------ */}
      <form className="auth-form" onSubmit={handleSubmit} style={{ marginBottom: "24px" }}>
        <label>
          Telegram User ID
          <input
            type="text"
            value={telegramUserId}
            onChange={e => setTelegramUserId(e.target.value)}
            placeholder="Ej: 123456789"
          />
        </label>
        <label>
          Telegram Username <span style={{ fontWeight: 400, color: "#6b7280" }}>(opcional)</span>
          <input
            type="text"
            value={telegramUsername}
            onChange={e => setTelegramUsername(e.target.value)}
            placeholder="Ej: @usuario"
          />
        </label>
        <label>
          User ID
          <input
            type="text"
            value={userId}
            onChange={e => setUserId(e.target.value)}
            placeholder="UUID del usuario del sistema"
          />
        </label>

        {formError && <p style={{ color: "red", margin: "4px 0" }}>{formError}</p>}

        <button type="submit" disabled={createMutation.isPending}>
          <MessageCircle size={16} />
          {createMutation.isPending ? "Vinculando…" : "Agregar vinculo"}
        </button>
      </form>

      {/* ------------------------------------------------------------------ */}
      {/* Status / errors                                                      */}
      {/* ------------------------------------------------------------------ */}
      {isLoading && <p className="loading-text">Cargando vinculos…</p>}
      {error && <p className="error-text">Error al cargar los vinculos de Telegram.</p>}
      {deleteMutation.isError && (
        <p className="error-text">Error al eliminar el vinculo.</p>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Table                                                                */}
      {/* ------------------------------------------------------------------ */}
      {data && data.items.length === 0 && (
        <p className="empty-text">No hay vinculos de Telegram registrados.</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Telegram User ID</th>
                <th>Username</th>
                <th>User ID</th>
                <th>Vinculado el</th>
                <th>Activo</th>
                <th>Accion</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: TelegramUserLinkRead) => (
                <tr key={item.id}>
                  <td className="cell-id">{item.telegram_user_id}</td>
                  <td>{item.telegram_username ?? "—"}</td>
                  <td className="cell-id">{item.user_id}</td>
                  <td className="cell-date">{formatDate(item.linked_at)}</td>
                  <td>
                    <span style={activeBadgeStyle(item.active)}>
                      {item.active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn-ghost"
                      onClick={() => deleteMutation.mutate(item.id)}
                      disabled={deleteMutation.isPending}
                      title="Eliminar vinculo"
                    >
                      <Trash2 size={15} />
                    </button>
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
