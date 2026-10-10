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
import { doctorsApi, DoctorRead } from "../../api/doctors";
import { useToast } from "../../components/Toast";

/** A doctor links himself: no admin can do it for him, so the useful thing to hand
 *  over is the instruction. */
const DOCTOR_INSTRUCTIONS =
  "Para recibir tus avisos de turnos por Telegram: abre el chat del bot, "
  + "escribe /start y luego tu numero de telefono sin guiones ni espacios "
  + "(ejemplo: 8091234567). Te pedira confirmar el numero.";

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
  const { addToast } = useToast();

  // --- Manual-link form state ---
  const [telegramUserId, setTelegramUserId] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [userId, setUserId] = useState("");

  // --- Invite-link state ---
  const [selectedUserId, setSelectedUserId] = useState("");
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showTokenSection, setShowTokenSection] = useState(false);

  // --- Queries ---
  const { data: links, isLoading, error } = useQuery({
    queryKey: ["telegram-links"],
    queryFn: () => telegramApi.listLinks(),
  });

  const { data: users } = useQuery({
    queryKey: ["telegram-linkable-users"],
    queryFn: async () => {
      const [admins, encargados] = await Promise.all([
        adminApi.listUsers("admin"),
        adminApi.listUsers("encargado"),
      ]);
      return [...admins, ...encargados].sort((a, b) => a.name.localeCompare(b.name));
    },
  });

  const { data: linkTokens } = useQuery({
    queryKey: ["telegram-link-tokens"],
    queryFn: () => telegramApi.listLinkTokens(),
  });

  // Telegram is the only notification channel, so knowing who is NOT linked is the
  // difference between "the system informed them" and "nobody was told".
  const { data: doctors } = useQuery({
    queryKey: ["doctors", "all", "reachability"],
    queryFn: () => doctorsApi.list("all"),
  });

  const [onlyUnreachable, setOnlyUnreachable] = useState(false);

  // Build user-id → name map for token table display
  const userMap = new Map<string, UserRead>();
  if (users) users.forEach((u) => userMap.set(u.id, u));

  // --- Reachability: who can actually be notified ---
  const allUsers = users ?? [];
  const allDoctors = doctors?.items ?? [];
  const linkedUsers = allUsers.filter((u) => u.telegram_chat_id);
  const linkedDoctors = allDoctors.filter((d) => d.has_telegram);
  const visibleUsers = onlyUnreachable
    ? allUsers.filter((u) => !u.telegram_chat_id)
    : allUsers;
  const visibleDoctors = onlyUnreachable
    ? allDoctors.filter((d) => !d.has_telegram)
    : allDoctors;

  // --- Mutations ---
  const createMutation = useMutation({
    mutationFn: (payload: CreateTelegramLinkRequest) =>
      telegramApi.createLink(payload),
    onSuccess: () => {
      setTelegramUserId("");
      setTelegramUsername("");
      setUserId("");
      addToast("success", "Vínculo creado.");
      void queryClient.invalidateQueries({ queryKey: ["telegram-links"] });
    },
    onError: (err: Error) => {
      addToast("error", err.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => telegramApi.deleteLink(id),
    onSuccess: () => {
      addToast("success", "Vínculo eliminado.");
      void queryClient.invalidateQueries({ queryKey: ["telegram-links"] });
    },
    onError: (err: Error) => {
      addToast("error", err.message || "Error al eliminar el vínculo.");
    },
  });

  const generateTokenMutation = useMutation({
    mutationFn: (uid: string) => telegramApi.generateLinkToken(uid),
    onSuccess: (data) => {
      setGeneratedLink(data.deep_link_url);
      setSelectedUserId("");
      setCopied(false);
      void queryClient.invalidateQueries({ queryKey: ["telegram-link-tokens"] });
    },
    onError: (err: Error) => {
      addToast("error", err.message);
    },
  });

  // --- Handlers ---
  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!telegramUserId.trim() || !userId.trim()) {
      addToast("error", "Los campos Telegram User ID y User ID son obligatorios.");
      return;
    }
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
      {/* Who can actually receive anything                                     */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="auth-form"
        style={{ marginBottom: "24px", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px" }}
      >
        <h3 style={{ marginTop: 0 }}>¿Quién puede recibir avisos?</h3>
        <p style={{ color: "#64748b", fontSize: "0.85rem", marginTop: 0 }}>
          Telegram es el <strong>único canal</strong>. A quien no esté vinculado no le llega nada:
          ni escalaciones, ni recordatorios, ni confirmaciones.
        </p>

        <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "12px", flexWrap: "wrap" }}>
          <label className="toggle-label" style={{ margin: 0 }}>
            <input
              type="checkbox"
              checked={onlyUnreachable}
              onChange={(e) => setOnlyUnreachable(e.target.checked)}
            />
            Ver solo los que NO reciben
          </label>
          <span style={{ fontSize: "0.85rem" }}>
            Usuarios: <strong>{linkedUsers.length}</strong> de {allUsers.length} ·{" "}
            Médicos: <strong>{linkedDoctors.length}</strong> de {allDoctors.length}
          </span>
        </div>

        {allUsers.length === 0 && allDoctors.length === 0 && <p className="loading-text">Cargando…</p>}

        {visibleUsers.length > 0 && (
          <>
            <h4 style={{ margin: "12px 0 6px", fontSize: "0.9rem" }}>Usuarios del sistema</h4>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr><th>Nombre</th><th>Rol</th><th>¿Recibe?</th><th></th></tr>
                </thead>
                <tbody>
                  {visibleUsers.map((u) => (
                    <tr key={u.id}>
                      <td>{u.name}</td>
                      <td>{u.role}</td>
                      <td>{u.telegram_chat_id ? "✅ Sí" : "❌ No"}</td>
                      <td>
                        {!u.telegram_chat_id && (
                          <button
                            className="btn-ghost"
                            style={{ padding: "3px 8px", fontSize: "0.8rem" }}
                            onClick={() => {
                              setSelectedUserId(u.id);
                              generateTokenMutation.mutate(u.id);
                            }}
                            disabled={generateTokenMutation.isPending}
                          >
                            Generar link
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {visibleDoctors.length > 0 && (
          <>
            <h4 style={{ margin: "16px 0 6px", fontSize: "0.9rem" }}>
              Médicos
              <span style={{ fontWeight: 400, color: "#64748b", fontSize: "0.8rem" }}>
                {" "}— solo ellos pueden vincularse, enviando su teléfono al bot
              </span>
            </h4>
            <div className="table-wrapper" style={{ maxHeight: "320px", overflowY: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr><th>Nombre</th><th>¿Recibe?</th><th></th></tr>
                </thead>
                <tbody>
                  {visibleDoctors.map((d: DoctorRead) => (
                    <tr key={d.id}>
                      <td>{d.name}</td>
                      <td>{d.has_telegram ? "✅ Sí" : "❌ No"}</td>
                      <td>
                        {!d.has_telegram && (
                          <button
                            className="btn-ghost"
                            style={{ padding: "3px 8px", fontSize: "0.8rem" }}
                            title="Copia las instrucciones para enviárselas al médico"
                            onClick={() => {
                              navigator.clipboard?.writeText(DOCTOR_INSTRUCTIONS);
                              addToast("success", "Instrucciones copiadas.");
                            }}
                          >
                            <Copy size={13} /> Instrucciones
                          </button>
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
            ID Telegram
            <input
              type="text"
              value={telegramUserId}
              onChange={(e) => setTelegramUserId(e.target.value)}
              placeholder="Ej: 123456789"
            />
          </label>
          <label>
            Usuario Telegram{" "}
            <span style={{ fontWeight: 400, color: "#6b7280" }}>(opcional)</span>
            <input
              type="text"
              value={telegramUsername}
              onChange={(e) => setTelegramUsername(e.target.value)}
              placeholder="Ej: @usuario"
            />
          </label>
          <label>
            ID Usuario
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="UUID del usuario del sistema"
            />
          </label>

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
                <th>Usuario</th>
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
                      onClick={() => deleteMutation.mutate(item.telegram_user_id)}
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
