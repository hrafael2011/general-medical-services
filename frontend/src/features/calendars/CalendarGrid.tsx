// frontend/src/features/calendars/CalendarGrid.tsx
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { calendarsApi, CalendarAssignmentRead } from "../../api/calendars";
import { doctorsApi, DoctorRead } from "../../api/doctors";
import type { ServiceAreaRead } from "../../api/doctors";
import { AssignDoctorModal } from "./AssignDoctorModal";
import { RemoveAssignmentPopover } from "./RemoveAssignmentPopover";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";

const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

interface AssignTarget { date: string; areaId: string; areaName: string; }
interface RemoveTarget { assignment: CalendarAssignmentRead; areaName: string; }

export function CalendarGrid() {
  const { calendarId } = useParams<{ calendarId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { addToast } = useToast();

  const [assignTarget, setAssignTarget] = useState<AssignTarget | null>(null);
  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null);
  const [generateSummary, setGenerateSummary] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["calendar-grid", calendarId],
    queryFn: () => calendarsApi.getGrid(calendarId!),
    enabled: !!calendarId,
  });

  const { data: doctorsData } = useQuery({
    queryKey: ["doctors", false],
    queryFn: () => doctorsApi.list(false),
    enabled: !!calendarId,
  });

  const { data: serviceAreasData } = useQuery({
    queryKey: ["service-areas"],
    queryFn: doctorsApi.listServiceAreas,
    enabled: !!calendarId,
  });

  const doctorMap: Record<string, DoctorRead> = {};
  for (const d of doctorsData?.items ?? []) doctorMap[d.id] = d;

  const areaMap: Record<string, string> = {};
  for (const a of (serviceAreasData ?? []) as ServiceAreaRead[]) areaMap[a.id] = a.display_name;

  const invalidate = () => qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });

  const approveMutation = useMutation({
    mutationFn: () => calendarsApi.approve(calendarId!),
    onSuccess: () => { invalidate(); addToast("success", "Calendario aprobado."); },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al aprobar."),
  });

  const newVersionMutation = useMutation({
    mutationFn: () => calendarsApi.newVersion(calendarId!),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Nueva versión creada.");
    },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al crear versión."),
  });

  const generateMutation = useMutation({
    mutationFn: () => calendarsApi.generate(calendarId!),
    onSuccess: (result) => {
      invalidate();
      setGenerateSummary(`Asignados: ${result.assigned_count} / Huecos: ${result.gap_count}`);
      addToast("success", "Calendario generado.");
    },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al generar."),
  });

  const assignMutation = useMutation({
    mutationFn: (doctorId: string) => calendarsApi.assignDoctor(calendarId!, data!.version.id, {
      service_date: assignTarget!.date,
      service_area_id: assignTarget!.areaId,
      doctor_id: doctorId,
    }),
    onSuccess: () => { invalidate(); setAssignTarget(null); addToast("success", "Médico asignado."); },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al asignar."),
  });

  const removeMutation = useMutation({
    mutationFn: () => calendarsApi.removeAssignment(calendarId!, data!.version.id, removeTarget!.assignment.id),
    onSuccess: () => { invalidate(); setRemoveTarget(null); addToast("success", "Asignación quitada."); },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al quitar."),
  });

  if (!calendarId) return null;
  if (isLoading) return <p className="loading-text">Cargando grilla…</p>;
  if (error || !data) return <p className="error-text">Error al cargar el calendario.</p>;

  const { calendar, version, slots } = data;
  const isDraft = version.status === "draft";

  const areas = [...new Set(slots.map(s => s.service_area_id))].sort();
  const days  = [...new Set(slots.map(s => s.service_date))].sort();
  const slotIndex = new Map(slots.map(s => [`${s.service_date}|${s.service_area_id}`, s]));

  function cellClass(slot: typeof slots[0] | undefined): string {
    if (!slot?.assignment) return isDraft ? "cell-empty-draft" : "cell-empty-approved";
    if (slot.assignment.assignment_source === "manual") return "cell-assigned-manual";
    return "cell-assigned-generated";
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <button className="btn-ghost" onClick={() => navigate("/calendars")}>← Volver</button>
        <h2 style={{ margin: 0, fontSize: 16 }}>
          Calendario {MONTHS[calendar.month - 1]} {calendar.year} — Versión {version.version_number}
        </h2>
        <span style={{
          padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 700,
          background: version.status === "approved" ? "#d1fae5" : "#f3f4f6",
          color: version.status === "approved" ? "#065f46" : "#6b7280",
        }}>
          {version.status === "approved" ? "Aprobado" : "Borrador"}
        </span>
        {isDraft && (
          <>
            <button className="btn-ghost" disabled={generateMutation.isPending} onClick={() => generateMutation.mutate()}>
              {generateMutation.isPending ? "Generando…" : "Generar calendario"}
            </button>
            <button className="btn-primary" disabled={approveMutation.isPending} onClick={() => approveMutation.mutate()}>
              {approveMutation.isPending ? "Aprobando…" : "Aprobar"}
            </button>
          </>
        )}
        {!isDraft && (
          <button className="btn-ghost" disabled={newVersionMutation.isPending} onClick={() => newVersionMutation.mutate()}>
            {newVersionMutation.isPending ? "Creando…" : "Nueva versión"}
          </button>
        )}
      </div>

      {generateSummary && (
        <p style={{ color: "#065f46", fontSize: 13, marginBottom: 8 }}>
          Generación completada — {generateSummary}
        </p>
      )}

      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ padding: "6px 10px", background: "#f8fafc", borderBottom: "2px solid #e2e8f0", textAlign: "left", whiteSpace: "nowrap" }}>Área</th>
              {days.map(d => (
                <th key={d} style={{ padding: "6px 8px", background: "#f8fafc", borderBottom: "2px solid #e2e8f0", textAlign: "center", minWidth: 80 }}>
                  {d.slice(8)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {areas.map(areaId => (
              <tr key={areaId}>
                <td style={{ padding: "6px 10px", borderBottom: "1px solid #f1f5f9", fontWeight: 600, whiteSpace: "nowrap" }}>{areaMap[areaId] ?? areaId}</td>
                {days.map(day => {
                  const slot = slotIndex.get(`${day}|${areaId}`);
                  const assignment = slot?.assignment ?? null;
                  const doctor = assignment ? doctorMap[assignment.doctor_id] : null;
                  const cls = cellClass(slot);
                  return (
                    <td
                      key={day}
                      className={cls}
                      style={{ padding: "6px 8px", borderBottom: "1px solid #f1f5f9", borderRight: "1px solid #f1f5f9", textAlign: "center" }}
                      onClick={() => {
                        if (!isDraft) return;
                        if (assignment) {
                          setRemoveTarget({ assignment, areaName: areaMap[areaId] ?? areaId });
                        } else {
                          setAssignTarget({ date: day, areaId, areaName: areaMap[areaId] ?? areaId });
                        }
                      }}
                    >
                      {doctor ? doctor.name.split(" ").slice(-1)[0] : (isDraft ? "+" : "—")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.gaps.length > 0 && (
        <div style={{ marginTop: 12, padding: "10px 14px", background: "#fff7ed", borderRadius: 6, border: "1px solid #fed7aa" }}>
          <strong style={{ fontSize: 13 }}>Huecos sin resolver: {data.gaps.length}</strong>
        </div>
      )}

      {assignTarget && (
        <AssignDoctorModal
          date={assignTarget.date}
          areaName={assignTarget.areaName}
          doctors={doctorsData?.items ?? []}
          onConfirm={doctorId => assignMutation.mutate(doctorId)}
          onClose={() => setAssignTarget(null)}
          isLoading={assignMutation.isPending}
        />
      )}

      {removeTarget && (
        <RemoveAssignmentPopover
          doctorName={doctorMap[removeTarget.assignment.doctor_id]?.name ?? removeTarget.assignment.doctor_id}
          date={removeTarget.assignment.service_date}
          areaName={removeTarget.areaName}
          source={removeTarget.assignment.assignment_source}
          onConfirm={() => removeMutation.mutate()}
          onClose={() => setRemoveTarget(null)}
          isLoading={removeMutation.isPending}
        />
      )}
    </div>
  );
}
