import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarAssignmentRead, calendarsApi, DaySlot } from "../../api/calendars";
import { ApiError } from "../../api/client";

const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

interface Props {
  calendarId: string;
  onBack: () => void;
}

export function CalendarGrid({ calendarId, onBack }: Props) {
  const queryClient = useQueryClient();
  const [rationaleDoc, setRationaleDoc] = useState<CalendarAssignmentRead | null>(null);
  const [generateSummary, setGenerateSummary] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["calendar-grid", calendarId],
    queryFn: () => calendarsApi.getGrid(calendarId),
  });

  const approveMutation = useMutation({
    mutationFn: () => calendarsApi.approve(calendarId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calendar-grid", calendarId] }),
  });

  const newVersionMutation = useMutation({
    mutationFn: () => {
      const reason = window.prompt("Motivo de la nueva versión (opcional):");
      return calendarsApi.newVersion(calendarId, reason ?? undefined);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });
      queryClient.invalidateQueries({ queryKey: ["calendars"] });
    },
  });

  const assignMutation = useMutation({
    mutationFn: ({ date, areaId }: { date: string; areaId: string }) => {
      const doctorId = window.prompt(`Asignar médico — ${date} / ${areaId}\n\nID del médico:`);
      if (!doctorId) return Promise.reject(new Error("cancelled"));
      return calendarsApi.assignDoctor(calendarId, data!.version.id, {
        service_date: date,
        service_area_id: areaId,
        doctor_id: doctorId.trim(),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calendar-grid", calendarId] }),
    onError: (err: unknown) => {
      if (err instanceof Error && err.message === "cancelled") return;
      alert(err instanceof ApiError ? err.message : "Error al asignar médico.");
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({ assignmentId }: { assignmentId: string }) =>
      calendarsApi.removeAssignment(calendarId, data!.version.id, assignmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calendar-grid", calendarId] }),
  });

  const generateMutation = useMutation({
    mutationFn: () => calendarsApi.generate(calendarId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });
      setGenerateError(null);
      setGenerateSummary(`Asignados: ${result.assigned_count} / Huecos: ${result.gap_count}`);
    },
    onError: (err: unknown) => {
      setGenerateSummary(null);
      setGenerateError(err instanceof ApiError ? err.message : "Error al generar el calendario.");
    },
  });

  if (isLoading) return <p style={{ padding: "1rem" }}>Cargando grilla…</p>;
  if (error || !data) return <p style={{ padding: "1rem", color: "#c00" }}>Error al cargar el calendario.</p>;

  const { calendar, version, slots } = data;

  // Collect unique areas and days
  const areas = [...new Set(slots.map(s => s.service_area_id))].sort();
  const days = [...new Set(slots.map(s => s.service_date))].sort();

  // Index slots by "date|area"
  const slotIndex = new Map<string, DaySlot>();
  for (const slot of slots) {
    slotIndex.set(`${slot.service_date}|${slot.service_area_id}`, slot);
  }

  const isDraft = version.status === "draft";

  return (
    <div style={{ padding: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
        <button className="btn-ghost" onClick={onBack}>← Volver</button>
        <h2 style={{ margin: 0, fontSize: 16 }}>
          Calendario {MONTHS[calendar.month - 1]} {calendar.year} — Versión {version.version_number}
        </h2>
        <span style={{
          display: "inline-block",
          padding: "2px 10px",
          borderRadius: 12,
          fontSize: 12,
          background: version.status === "approved" ? "#d1fae5" : "#f3f4f6",
          color: version.status === "approved" ? "#065f46" : "#6b7280",
          fontWeight: 600,
        }}>
          {version.status === "approved" ? "Aprobado" : "Borrador"}
        </span>

        {isDraft && (
          <>
            <button
              className="btn-ghost"
              style={{ fontSize: 13 }}
              disabled={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              {generateMutation.isPending ? "Generando…" : "Generar calendario"}
            </button>
            <button
              className="btn-primary"
              style={{ fontSize: 13 }}
              disabled={approveMutation.isPending}
              onClick={() => approveMutation.mutate()}
            >
              {approveMutation.isPending ? "Aprobando…" : "Aprobar"}
            </button>
          </>
        )}

        {!isDraft && (
          <button
            className="btn-ghost"
            style={{ fontSize: 13 }}
            disabled={newVersionMutation.isPending}
            onClick={() => newVersionMutation.mutate()}
          >
            {newVersionMutation.isPending ? "Creando…" : "Nueva versión"}
          </button>
        )}
      </div>

      {generateSummary && (
        <p style={{ margin: "0.25rem 0 0.5rem", fontSize: 13, color: "#065f46" }}>
          Generación completada — {generateSummary}
        </p>
      )}
      {generateError && (
        <p style={{ margin: "0.25rem 0 0.5rem", fontSize: 13, color: "#c00" }}>
          {generateError}
        </p>
      )}

      {slots.length === 0 ? (
        <div style={{ color: "#888", padding: "1rem 0" }}>
          <p>No hay asignaciones aún.</p>
          {isDraft && (
            <p style={{ fontSize: 13 }}>
              Haz clic en una celda de la tabla para asignar un médico.
            </p>
          )}
        </div>
      ) : null}

      {days.length === 0 && areas.length === 0 ? (
        <div style={{ overflowX: "auto", marginTop: "0.5rem" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                <th style={thStyle}>Área</th>
                {Array.from({ length: new Date(calendar.year, calendar.month, 0).getDate() }, (_, i) => (
                  <th key={i + 1} style={{ ...thStyle, width: 36 }}>{i + 1}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={35} style={{ padding: "1rem", color: "#888", textAlign: "center" }}>
                  Sin asignaciones — usa el botón de asignar médico
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ overflowX: "auto", marginTop: "0.5rem" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                <th style={thStyle}>Área</th>
                {days.map(d => (
                  <th key={d} style={{ ...thStyle, width: 90 }}>
                    {d.slice(8)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {areas.map(area => (
                <tr key={area}>
                  <td style={{ ...tdStyle, fontWeight: 600, whiteSpace: "nowrap" }}>{area}</td>
                  {days.map(day => {
                    const slot = slotIndex.get(`${day}|${area}`);
                    const assignment = slot?.assignment ?? null;
                    return (
                      <td
                        key={day}
                        style={{
                          ...tdStyle,
                          cursor: isDraft ? "pointer" : "default",
                          background: assignment ? "#f0fdf4" : isDraft ? "#fafafa" : undefined,
                          color: assignment ? "#065f46" : "#aaa",
                          textAlign: "center",
                        }}
                        title={
                          assignment
                            ? `${assignment.doctor_id}${assignment.override_justification ? ` (override: ${assignment.override_justification})` : ""}`
                            : isDraft ? "Clic para asignar" : "—"
                        }
                        onClick={() => {
                          if (!isDraft) return;
                          if (assignment) {
                            if (window.confirm(`Quitar asignación del médico ${assignment.doctor_id}?`)) {
                              removeMutation.mutate({ assignmentId: assignment.id });
                            }
                          } else {
                            assignMutation.mutate({ date: day, areaId: area });
                          }
                        }}
                      >
                        {assignment ? (
                          <>
                            <div>{assignment.doctor_id.slice(0, 8) + "…"}</div>
                            {assignment.rationale && (
                              <button
                                style={{
                                  background: "none",
                                  border: "none",
                                  padding: 0,
                                  fontSize: 11,
                                  color: "#2563eb",
                                  cursor: "pointer",
                                  textDecoration: "underline",
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRationaleDoc(assignment);
                                }}
                              >
                                (razón)
                              </button>
                            )}
                          </>
                        ) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.gaps.length > 0 && (
        <div style={{ marginTop: "1rem", padding: "0.75rem 1rem", background: "#fff7ed", borderRadius: 6, border: "1px solid #fed7aa" }}>
          <strong style={{ fontSize: 13 }}>Huecos sin resolver ({data.gaps.length})</strong>
        </div>
      )}

      {rationaleDoc && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setRationaleDoc(null)}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 8,
              padding: "1.5rem",
              maxWidth: 480,
              width: "90%",
              maxHeight: "80vh",
              overflowY: "auto",
              boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <strong style={{ fontSize: 14 }}>Razón de asignación</strong>
              <button
                style={{
                  background: "none",
                  border: "none",
                  fontSize: 18,
                  cursor: "pointer",
                  lineHeight: 1,
                  color: "#555",
                }}
                onClick={() => setRationaleDoc(null)}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>
            <p style={{ fontSize: 12, color: "#666", margin: "0 0 0.75rem" }}>
              Médico: <strong>{rationaleDoc.doctor_id}</strong> — {rationaleDoc.service_date}
            </p>
            {rationaleDoc.rationale ? (
              <dl style={{ margin: 0, fontSize: 13, display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.3rem 0.75rem" }}>
                {Object.entries(rationaleDoc.rationale).map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt style={{ fontWeight: 600, color: "#374151", wordBreak: "break-word" }}>{key}</dt>
                    <dd style={{ margin: 0, color: "#555", wordBreak: "break-word" }}>
                      {typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
                    </dd>
                  </React.Fragment>
                ))}
              </dl>
            ) : (
              <p style={{ fontSize: 13, color: "#888" }}>Sin razón disponible.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "0.4rem 0.5rem",
  borderBottom: "2px solid #e0e0e0",
  textAlign: "left",
  background: "#f9fafb",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "0.35rem 0.5rem",
  borderBottom: "1px solid #eee",
  borderRight: "1px solid #eee",
};
