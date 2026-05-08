import { useQuery } from "@tanstack/react-query";
import { calendarsApi, CalendarRead } from "../../api/calendars";
import { doctorsApi } from "../../api/doctors";
import { AlertCard } from "./AlertCard";
import { KpiCard } from "./KpiCard";

const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

function deriveAlerts(calendars: CalendarRead[]) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const nextMonth = month === 12 ? 1 : month + 1;
  const nextYear = month === 12 ? year + 1 : year;

  const alerts: Array<{ severity: "warning"|"success"|"info"; icon: string; title: string; detail?: string; actionLabel?: string; actionTo?: string }> = [];

  const current = calendars.find(c => c.year === year && c.month === month);
  const next = calendars.find(c => c.year === nextYear && c.month === nextMonth);

  if (!current) {
    alerts.push({ severity: "info", icon: "ℹ️", title: "No hay calendario para este mes", actionLabel: "Crear", actionTo: "/calendars" });
  } else if (current.status === "approved") {
    alerts.push({ severity: "success", icon: "✅", title: `Calendario ${MONTHS[month - 1]} aprobado`, detail: "Cobertura activa para el mes en curso." });
  } else if (current.status === "draft") {
    alerts.push({ severity: "warning", icon: "⚠️", title: `Calendario ${MONTHS[month - 1]} en borrador`, detail: "Pendiente de generación o aprobación.", actionLabel: "Ver", actionTo: `/calendars/${current.id}` });
  }

  if (!next) {
    alerts.push({ severity: "warning", icon: "⚠️", title: `Calendario ${MONTHS[nextMonth - 1]} no creado`, detail: "Crealo antes de que inicie el mes.", actionLabel: "Crear", actionTo: "/calendars" });
  }

  return alerts;
}

export function DashboardView() {
  const { data: calendars = [], isLoading: loadingCals } = useQuery({
    queryKey: ["calendars"],
    queryFn: calendarsApi.list,
  });

  const { data: doctors } = useQuery({
    queryKey: ["doctors", false],
    queryFn: () => doctorsApi.list(false),
  });

  const activeCount = doctors?.items.filter(d => d.service_active).length ?? 0;

  const now = new Date();
  const currentCal = calendars.find(c => c.year === now.getFullYear() && c.month === now.getMonth() + 1);
  const alerts = deriveAlerts(calendars);

  return (
    <div className="dashboard">
      <div>
        <p className="dashboard-section-title">Estado del sistema</p>
        <div className="alert-cards">
          {loadingCals ? (
            <p className="loading-text">Cargando…</p>
          ) : alerts.map((a, i) => (
            <AlertCard key={i} {...a} />
          ))}
        </div>
      </div>

      <div>
        <p className="dashboard-section-title">Métricas</p>
        <div className="kpi-grid">
          <KpiCard value={activeCount} label="Médicos activos" />
          <KpiCard value={currentCal ? (currentCal.status === "approved" ? "Aprobado" : "Borrador") : "Sin generar"} label="Estado del mes" />
          <KpiCard value="—" label="Huecos sin resolver" />
        </div>
      </div>
    </div>
  );
}
