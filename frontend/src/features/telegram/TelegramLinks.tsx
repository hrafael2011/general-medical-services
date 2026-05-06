import { Check, Copy, MessageCircle, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  telegramApi,
  TelegramUserLinkRead,
  CreateTelegramLinkRequest,
  LinkTokenRead,
} from "../../api/telegram";
import { adminApi, UserRead } from "../../api/admin";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-DO", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function formatExpiry(iso: string) {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return "Expirado";
  const hours = Math.round(diff / 3600000);
  if (hours < 1) return "< 1h";
  return `${hours}h`;
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

function tokenBadge(token: LinkTokenRead): React.CSSProperties {
  if (token.used_at) return activeBadgeStyle(false);
  if (!token.active) return activeBadgeStyle(false);
  if (new Date(token.expires_at).getTime() <= Date.now()) {
    return activeBadgeStyle(false);
  }
  return activeBadgeStyle(true);
}

function tokenLabel(token: LinkTokenRead): string {
  if (token.used_at) return "Usado";
  if (!token.active) return "Inactivo";
  if (new Date(token.expires_at).getTime() <= Date.now()) return "Expirado";
  return "Activo";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TelegramLinks() {
  const queryClient = useQueryClient();

  // --- Manual-link form state ---
  const [telegramUserId, setTelegramUserId] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [userId, setUserId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // --- Invite-link state ---
  const [selectedUserId, setSelectedUserId] = useState("");
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [showTokenSection, setShowTokenSection] = useState(false);

  // --- Queries ---
  const { data: links, isLoading, error } = useQuery({
    queryKey: ["telegram-links"],
    queryFn: () => telegramApi.listLinks(),
  });

  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: () => adminApi.listUsers("doctor"),
  });

  const { data: linkTokens } = useQuery({
    queryKey: ["telegram-link-tokens"],
    queryFn: () => telegramApi.listLinkTokens(),
  });

  // Build user-id → name map for token table display
  const userMap = new Map<string, UserRead>();
  if (users) users.forEach((u) => userMap.set(u.id, u));

  // --- Mutations ---
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

  const generateTokenMutation = useMutation({
    mutationFn: (uid: string) => telegramApi.generateLinkToken(uid),
    onSuccess: (data) => {
      setGeneratedLink(data.deep_link_url);
      setSelectedUserId("");
      setCopied(false);
      setTokenError(null);
      void queryClient.invalidateQueries({ queryKey: ["telegram-link-tokens"] });
    },
    onError: (err: Error) => {
      setTokenError(err.message);
    },
  });

  // --- Handlers ---
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

  function handleGenerateLink() {
    if (!selectedUserId) return;
    generateTokenMutation.mutate(selectedUserId);
  }

  function copyDeepLink() {
    if (!generatedLink) return;
    navigator.clipboard.writeText(generatedLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // --- Render ---
  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <MessageCircle size={20} />
          <h2>Telegram — Vinculos de usuario</h2>
          {links && <span className="count-badge">{links.length}</span>}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Invite-link generation                                                */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="auth-form"
        style={{ marginBottom: "24px", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" }}
      >
        <h3 style={{ marginTop: 0 }}>Generar link de invitacion</h3>

        <label>
          Usuario del sistema
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
          >
            <option value="">-- Seleccionar usuario --</option>
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.email})
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={handleGenerateLink}
          disabled={!selectedUserId || generateTokenMutation.isPending}
        >
          <MessageCircle size={16} />
          {generateTokenMutation.isPending ? "Generando…" : "Generar link"}
        </button>

        {tokenError && <p style={{ color: "red", margin: "4px 0" }}>{tokenError}</p>}

        {generatedLink && (
          <div
            style={{
              marginTop: "12px",
              padding: "12px",
              background: "#f3f4f6",
              borderRadius: "6px",
            }}
          >
            <p style={{ fontSize: "0.85rem", margin: "0 0 4px", color: "#6b7280" }}>
              Link de invitacion (expira en 24h):
            </p>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <code
                style={{
                  flex: 1,
                  wordBreak: "break-all",
                  fontSize: "0.85rem",
                  padding: "6px",
                  background: "#fff",
                  borderRadius: "4px",
                  border: "1px solid #d1d5db",
                }}
              >
                {generatedLink}
              </code>
              <button className="btn-ghost" onClick={copyDeepLink} title="Copiar link">
                {copied ? <Check size={15} color="green" /> : <Copy size={15} />}
              </button>
            </div>
          </div>
        )}

        {/* Toggle to show active tokens */}
        {linkTokens && linkTokens.length > 0 && (
          <button
            className="btn-ghost"
            type="button"
            onClick={() => setShowTokenSection(!showTokenSection)}
            style={{ marginTop: "12px", fontSize: "0.85rem" }}
          >
            {showTokenSection ? "Ocultar" : "Mostrar"} tokens activos ({linkTokens.length})
          </button>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Link tokens table (collapsible)                                      */}
      {/* ------------------------------------------------------------------ */}
      {showTokenSection && linkTokens && linkTokens.length > 0 && (
        <div className="table-wrapper" style={{ marginBottom: "24px" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Token</th>
                <th>Creado</th>
                <th>Expira</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {linkTokens.map((token: LinkTokenRead) => {
                const user = userMap.get(token.user_id);
                return (
                  <tr key={token.id}>
                    <td>{user ? user.name : token.user_id.slice(0, 8)}</td>
                    <td className="cell-id">
                      <code style={{ fontSize: "0.8rem" }}>
                        {token.token.slice(0, 16)}…
                      </code>
                    </td>
                    <td className="cell-date">{formatDate(token.created_at)}</td>
                    <td className="cell-date">{formatExpiry(token.expires_at)}</td>
                    <td>
                      <span style={tokenBadge(token)}>{tokenLabel(token)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Manual-link form                                                      */}
      {/* ------------------------------------------------------------------ */}
      <details style={{ marginBottom: "24px" }}>
        <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: "0.9rem" }}>
          Vinculacion manual (admin)
        </summary>
        <form className="auth-form" onSubmit={handleSubmit} style={{ marginTop: "12px" }}>
          <label>
            Telegram User ID
            <input
              type="text"
              value={telegramUserId}
              onChange={(e) => setTelegramUserId(e.target.value)}
              placeholder="Ej: 123456789"
            />
          </label>
          <label>
            Telegram Username{" "}
            <span style={{ fontWeight: 400, color: "#6b7280" }}>(opcional)</span>
            <input
              type="text"
              value={telegramUsername}
              onChange={(e) => setTelegramUsername(e.target.value)}
              placeholder="Ej: @usuario"
            />
          </label>
          <label>
            User ID
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="UUID del usuario del sistema"
            />
          </label>

          {formError && <p style={{ color: "red", margin: "4px 0" }}>{formError}</p>}

          <button type="submit" disabled={createMutation.isPending}>
            <MessageCircle size={16} />
            {createMutation.isPending ? "Vinculando…" : "Agregar vinculo"}
          </button>
        </form>
      </details>

      {/* ------------------------------------------------------------------ */}
      {/* Status / errors                                                      */}
      {/* ------------------------------------------------------------------ */}
      {isLoading && <p className="loading-text">Cargando vinculos…</p>}
      {error && <p className="error-text">Error al cargar los vinculos de Telegram.</p>}
      {deleteMutation.isError && (
        <p className="error-text">Error al eliminar el vinculo.</p>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Links table                                                          */}
      {/* ------------------------------------------------------------------ */}
      {links && links.length === 0 && (
        <p className="empty-text">No hay vinculos de Telegram registrados.</p>
      )}

      {links && links.length > 0 && (
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
              {links.map((item: TelegramUserLinkRead) => (
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
