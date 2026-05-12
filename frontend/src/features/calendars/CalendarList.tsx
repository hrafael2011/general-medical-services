import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Settings } from "lucide-react";
import { CalendarRead, calendarsApi } from "../../api/calendars";
import { ApiError } from "../../api/client";
import { useToast } from "../../components/Toast";

const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

const currentYear = new Date().getFullYear();

const GENERATION_MODE_LABELS: Record<CalendarRead["generation_mode"], string> = {
  manual: "Manual",
  assisted_auto: "Reglas",
  scheduled_auto: "Auto",
};

const GENERATION_MODE_TITLES: Record<CalendarRead["generation_mode"], string> = {
  manual: "Creado manualmente",
  assisted_auto: "Generado con reglas",
  scheduled_auto: "Generado por programación automática",
};

interface Props {
  onSelect: (calendarId: string) => void;
}

export function CalendarList({ onSelect }: Props) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formMonth, setFormMonth] = useState(new Date().getMonth() + 1);
  const [formYear, setFormYear] = useState(currentYear);
  const [error, setError] = useState<string | null>(null);
  const { addToast } = useToast();

  const { data: calendars = [], isLoading } = useQuery({
    queryKey: ["calendars"],
    queryFn: () => calendarsApi.list(),
  });

  const { data: generationSettings } = useQuery({
    queryKey: ["calendar-generation-settings"],
    queryFn: () => calendarsApi.getGenerationSettings(),
  });

  const settingsMutation = useMutation({
    mutationFn: calendarsApi.updateGenerationSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-generation-settings"] });
      addToast("success", "Configuración guardada.");
    },
    onError: (err: unknown) => {
      addToast("error", err instanceof ApiError ? err.message : "Error al guardar configuración.");
    },
  });

  const createMutation = useMutation({
    mutationFn: () => calendarsApi.create(formYear, formMonth),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendars"] });
      setShowForm(false);
      setError(null);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Error al crear calendario.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (calendarId: string) => calendarsApi.delete(calendarId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Calendario eliminado.");
    },
    onError: (err: unknown) => {
      addToast("error", err instanceof ApiError ? err.message : "Error al eliminar calendario.");
    },
  });

  function handleDelete(cal: CalendarRead) {
    const period = `${MONTHS[cal.month - 1]} ${cal.year}`;
    if (window.confirm(`¿Eliminar calendario de ${period}? Los datos se conservarán pero dejará de mostrarse.`)) {
      deleteMutation.mutate(cal.id);
    }
  }

  if (isLoading) return <p style={{ padding: "1rem" }}>Cargando calendarios…</p>;

  return (
    <div style={{ padding: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h2 style={{ margin: 0 }}>Calendarios</h2>
        <button className="btn-primary" onClick={() => setShowForm(s => !s)}>
          <CalendarPlus size={16} /> Nuevo borrador
        </button>
      </div>

      {showForm && (
        <div style={{ background: "#f9f9f9", border: "1px solid #ddd", borderRadius: 6, padding: "1rem", marginBottom: "1rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end", flexWrap: "wrap" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Mes
              <select value={formMonth} onChange={e => setFormMonth(Number(e.target.value))} style={{ padding: "0.35rem 0.5rem" }}>
                {MONTHS.map((m, i) => (
                  <option key={i + 1} value={i + 1}>{m}</option>
                ))}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Año
              <input
                type="number"
                value={formYear}
                onChange={e => setFormYear(Number(e.target.value))}
                min={2020}
                max={2100}
                style={{ padding: "0.35rem 0.5rem", width: 90 }}
              />
            </label>
            <button
              className="btn-primary"
              disabled={createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? "Creando…" : "Crear borrador manual"}
            </button>
            <button className="btn-ghost" onClick={() => { setShowForm(false); setError(null); }}>
              Cancelar
            </button>
          </div>
          {error && <p style={{ color: "#c00", marginTop: "0.5rem", fontSize: 13 }}>{error}</p>}
        </div>
      )}

      {generationSettings && (
        <section style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: "0.75rem 1rem", marginBottom: "1rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Settings size={18} color="#475569" />
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600 }}>
              <input
                type="checkbox"
                checked={generationSettings.auto_generation_enabled}
                disabled={settingsMutation.isPending}
                onChange={e => settingsMutation.mutate({ auto_generation_enabled: e.target.checked })}
              />
              Auto-generar borrador
            </label>
            <span style={{ fontSize: 12, color: generationSettings.auto_generation_enabled ? "#166534" : "#64748b", fontWeight: 700 }}>
              {generationSettings.auto_generation_enabled ? "Activo" : "Inactivo"}
            </span>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#555" }}>
            Día
            <select
              value={generationSettings.generation_day}
              disabled={settingsMutation.isPending}
              onChange={e => settingsMutation.mutate({ generation_day: Number(e.target.value) })}
              style={{ padding: "0.35rem 0.5rem", width: 72 }}
              aria-label="Día de generación automática"
            >
              {Array.from({ length: 28 }, (_, index) => index + 1).map(day => (
                <option key={day} value={day}>{day}</option>
              ))}
            </select>
          </label>
        </section>
      )}

      {calendars.length === 0 ? (
        <p style={{ color: "#888" }}>No hay calendarios registrados.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e0e0e0", textAlign: "left" }}>
              <th style={{ padding: "0.5rem 0.75rem" }}>Periodo</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Estado</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Modo</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Creado</th>
              <th style={{ padding: "0.5rem 0.75rem" }}></th>
            </tr>
          </thead>
          <tbody>
            {calendars.map((cal: CalendarRead) => (
              <tr key={cal.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600 }}>
                  {MONTHS[cal.month - 1]} {cal.year}
                </td>
                <td style={{ padding: "0.5rem 0.75rem" }}>
                  <span style={{
                    display: "inline-block",
                    padding: "2px 10px",
                    borderRadius: 12,
                    fontSize: 12,
                    background: cal.status === "approved" ? "#d1fae5" : "#f3f4f6",
                    color: cal.status === "approved" ? "#065f46" : "#6b7280",
                    fontWeight: 600,
                  }}>
                    {cal.status === "approved" ? "Aprobado" : "Borrador"}
                  </span>
                </td>
                <td style={{ padding: "0.5rem 0.75rem", color: "#555" }}>
                  <span title={GENERATION_MODE_TITLES[cal.generation_mode] ?? "Creado manualmente"} style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    borderRadius: 6,
                    fontSize: 12,
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    color: "#475569",
                    fontWeight: 700,
                  }}>
                    {GENERATION_MODE_LABELS[cal.generation_mode] ?? "Manual"}
                  </span>
                </td>
                <td style={{ padding: "0.5rem 0.75rem", color: "#555" }}>
                  {new Date(cal.created_at).toLocaleDateString("es-DO")}
                </td>
                <td style={{ padding: "0.5rem 0.75rem", display: "flex", gap: 8 }}>
                  <button className="btn-ghost" style={{ fontSize: 13 }} onClick={() => onSelect(cal.id)}>
                    Ver grilla →
                  </button>
                  <button
                    className="btn-ghost"
                    style={{ fontSize: 13, color: "#b91c1c" }}
                    onClick={() => handleDelete(cal)}
                    disabled={deleteMutation.isPending}
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
