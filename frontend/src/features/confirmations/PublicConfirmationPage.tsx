import { AlertTriangle, CheckCircle2, Inbox, MessageCircle } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { confirmationsApi } from "../../api/confirmations";

function typeLabel(type: string) {
  return type === "mission" ? "misión" : "servicio";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pendiente",
    received: "Recibido",
    confirmed: "Confirmado",
    expired: "Vencido",
  };
  return labels[status] ?? status;
}

export function PublicConfirmationPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [note, setNote] = useState("");

  const confirmation = useQuery({
    queryKey: ["public-confirmation", token],
    queryFn: () => confirmationsApi.getPublicConfirmation(token),
    enabled: Boolean(token),
    retry: false,
  });

  const response = useMutation({
    mutationFn: (action: "received" | "confirm") =>
      confirmationsApi.respondPublicConfirmation(token, action, note),
    onSuccess: () => {
      setNote("");
      void confirmation.refetch();
    },
  });

  const data = response.data ?? confirmation.data;
  const isFinal = data?.status === "confirmed";
  const assignmentLabel = typeLabel(data?.confirmation_type ?? "service");

  return (
    <main className="app-shell">
      <section className="auth-panel" aria-labelledby="confirmation-title">
        <header className="auth-header">
          <div className="status-icon"><CheckCircle2 size={28} /></div>
          <div>
            <p className="eyebrow">Confirmación médica</p>
            <h1 id="confirmation-title">Respuesta de servicio o misión</h1>
            <p className="summary">
              {data
                ? `${data.doctor_name ?? "Médico asignado"} · ${typeLabel(data.confirmation_type)} · ${statusLabel(data.status)}`
                : "Validando solicitud."}
            </p>
          </div>
        </header>

        {!token && (
          <div className="empty-state">
            <AlertTriangle size={22} />
            <p>El enlace de confirmación no contiene un token válido.</p>
          </div>
        )}

        {confirmation.isError && (
          <div className="empty-state">
            <AlertTriangle size={22} />
            <p>No se encontró una solicitud de confirmación válida.</p>
          </div>
        )}

        {confirmation.isLoading && <p className="summary">Cargando confirmación...</p>}

        {data && (
          <>
          {data.status !== "confirmed" && (
            <div className="info-banner" style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", background: "#eff6ff", borderRadius: "8px", marginBottom: "16px", color: "#1e40af", fontSize: "0.9rem" }}>
              <MessageCircle size={16} />
              <span>También puede confirmar respondiendo &quot;1&quot; al mensaje de WhatsApp que recibió.</span>
            </div>
          )}
          <div className="auth-form">
            <label>
              Nota opcional
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={3}
                maxLength={500}
                disabled={isFinal || response.isPending}
              />
            </label>

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => response.mutate("received")}
                disabled={isFinal || response.isPending}
              >
                <Inbox size={18} /> Confirmar recibido
              </button>
              <button
                type="button"
                onClick={() => response.mutate("confirm")}
                disabled={isFinal || response.isPending}
              >
                <CheckCircle2 size={18} /> Confirmar {assignmentLabel}
              </button>
            </div>

            {response.isError && (
              <p className="summary">No se pudo registrar la respuesta. Intente nuevamente.</p>
            )}
          </div>
          </>
        )}
      </section>
    </main>
  );
}
