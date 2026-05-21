import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check, Clock, ExternalLink, RefreshCw, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { actionAlertsApi, ActionAlertRead } from "../api/actionAlerts";
import { confirmationsApi } from "../api/confirmations";
import { useToast } from "./Toast";

const SECTION_LABELS: Record<string, string> = {
  missions: "Misiones",
  calendar: "Calendarios",
  notifications: "Notificaciones",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-DO", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function severityLabel(severity: string) {
  if (severity === "critical") return "Crítica";
  if (severity === "warning") return "Advertencia";
  return severity;
}

export function AlertBell() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const { data: summary } = useQuery({
    queryKey: ["action-alerts-summary"],
    queryFn: actionAlertsApi.summary,
    refetchInterval: 60_000,
  });

  const { data: alerts, isLoading } = useQuery({
    queryKey: ["action-alerts", "open"],
    queryFn: () => actionAlertsApi.list("open", 10),
    enabled: open,
  });

  const refreshAlerts = () => {
    void queryClient.invalidateQueries({ queryKey: ["action-alerts"] });
    void queryClient.invalidateQueries({ queryKey: ["action-alerts-summary"] });
  };

  const processOverdue = useMutation({
    mutationFn: confirmationsApi.processOverdue,
    onSuccess: result => {
      refreshAlerts();
      addToast(
        "info",
        `Confirmaciones vencidas: ${result.expired}. Alertas nuevas: ${result.alerts_created}.`,
      );
    },
    onError: () => addToast("error", "Error al revisar confirmaciones vencidas."),
  });

  const resolveAlert = useMutation({
    mutationFn: actionAlertsApi.resolve,
    onSuccess: () => {
      refreshAlerts();
      addToast("success", "Alerta marcada como resuelta.");
    },
    onError: () => addToast("error", "Error al resolver la alerta."),
  });

  const dismissAlert = useMutation({
    mutationFn: actionAlertsApi.dismiss,
    onSuccess: () => {
      refreshAlerts();
      addToast("success", "Alerta descartada.");
    },
    onError: () => addToast("error", "Error al descartar la alerta."),
  });

  const totalOpen = summary?.total_open ?? 0;

  function goToAlert(alert: ActionAlertRead) {
    if (alert.action_url) {
      navigate(alert.action_url);
      setOpen(false);
    }
  }

  return (
    <div className="alert-bell">
      <button
        className="alert-bell-button"
        onClick={() => setOpen(value => !value)}
        aria-label={`Alertas accionables${totalOpen ? `: ${totalOpen}` : ""}`}
      >
        <Bell size={18} />
        {totalOpen > 0 && <span className="alert-bell-badge">{totalOpen}</span>}
      </button>

      {open && (
        <div className="alert-menu" role="dialog" aria-label="Alertas accionables">
          <div className="alert-menu-header">
            <div>
              <strong>Alertas</strong>
              <span>{totalOpen} abiertas</span>
            </div>
            <button
              className="icon-button"
              onClick={() => processOverdue.mutate()}
              disabled={processOverdue.isPending}
              title="Revisar confirmaciones vencidas"
            >
              <RefreshCw size={15} />
            </button>
          </div>

          {isLoading && <p className="alert-menu-empty">Cargando alertas…</p>}

          {!isLoading && alerts && alerts.items.length === 0 && (
            <p className="alert-menu-empty">No hay alertas pendientes.</p>
          )}

          {alerts && alerts.items.length > 0 && (
            <div className="alert-menu-list">
              {alerts.items.map(alert => (
                <article key={alert.id} className={`alert-menu-item alert-${alert.severity}`}>
                  <div className="alert-item-top">
                    <span className="alert-severity">{severityLabel(alert.severity)}</span>
                    <span>{SECTION_LABELS[alert.section] ?? alert.section}</span>
                  </div>
                  <h3>{alert.title}</h3>
                  <p>{alert.message}</p>
                  <span className="alert-date">
                    <Clock size={13} /> {formatDate(alert.created_at)}
                  </span>
                  <div className="alert-actions">
                    {alert.action_url && (
                      <button className="btn-ghost" onClick={() => goToAlert(alert)}>
                        <ExternalLink size={14} /> Abrir
                      </button>
                    )}
                    <button className="btn-ghost" onClick={() => resolveAlert.mutate(alert.id)}>
                      <Check size={14} /> Resolver
                    </button>
                    <button className="btn-ghost" onClick={() => dismissAlert.mutate(alert.id)}>
                      <X size={14} /> Descartar
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
