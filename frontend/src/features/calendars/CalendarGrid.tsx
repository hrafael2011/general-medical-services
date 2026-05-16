// frontend/src/features/calendars/CalendarGrid.tsx
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileDown, Trash2, Wand2 } from "lucide-react";
import { calendarsApi, CalendarAssignmentRead, DaySlot, WeekRead } from "../../api/calendars";
import { doctorsApi, availabilityApi, DoctorRead, RankRead } from "../../api/doctors";
import type { ServiceAreaRead } from "../../api/doctors";
import { AssignDoctorModal } from "./AssignDoctorModal";
import { RemoveAssignmentPopover } from "./RemoveAssignmentPopover";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";

const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

const GENERATION_MODE_LABELS = {
  manual: "Manual",
  assisted_auto: "Generado con reglas",
  scheduled_auto: "Auto programado",
} as const;

interface AssignTarget { date: string; areaId: string; areaName: string; currentAssignmentId?: string; currentDoctorId?: string; }
interface RemoveTarget { assignment: CalendarAssignmentRead; areaName: string; }
interface AssignPayload { doctorId: string; overrideJustification?: string | null; }

interface CalendarDay {
  day: number | null;       // null for padding days outside month
  dateStr: string | null;   // "2026-05-14" or null
}

function buildCalendarDays(year: number, month: number): CalendarDay[] {
  // month is 1-indexed (1=January)
  const daysInMonth = new Date(year, month, 0).getDate();
  // getDay(): 0=Sun, 1=Mon, ..., 6=Sat → we want Mon-first
  const firstDay = new Date(year, month - 1, 1).getDay();
  // Convert JS Sunday=0 to Monday=0 offset
  const offset = firstDay === 0 ? 6 : firstDay - 1;

  const days: CalendarDay[] = [];

  // Padding days before month start
  for (let i = 0; i < offset; i++) {
    days.push({ day: null, dateStr: null });
  }

  // Actual days of the month
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    days.push({ day: d, dateStr });
  }

  // Pad remaining cells to complete the last week
  while (days.length % 7 !== 0) {
    days.push({ day: null, dateStr: null });
  }

  return days;
}

function chunkIntoWeeks(days: CalendarDay[]): CalendarDay[][] {
  const weeks: CalendarDay[][] = [];
  for (let i = 0; i < days.length; i += 7) {
    weeks.push(days.slice(i, i + 7));
  }
  return weeks;
}

interface AreaAssignment {
  areaId: string;
  areaName: string;
  slot: DaySlot | null;   // null if no assignment for this area on this day
}

// Returns, for a given date string, the array of all service areas with their assignment status.
function getDayAssignments(
  dateStr: string,
  slots: DaySlot[],
  areaMap: Record<string, string>,
  sortedAreaIds: string[],
): AreaAssignment[] {
  return sortedAreaIds.map((areaId) => ({
    areaId,
    areaName: areaMap[areaId] ?? areaId,
    slot: slots.find((s) => s.service_date === dateStr && s.service_area_id === areaId) ?? null,
  }));
}

const AREA_COLOR_MAP: Record<string, string> = {
  Emergencia: "#dc2626",
  Pista: "#2563eb",
  Disponible: "#16a34a",
};

function areaColor(areaName: string): string {
  return AREA_COLOR_MAP[areaName] ?? "#6b7280";
}

function rankDisplayName(rankName: string): string {
  return rankName.toUpperCase();
}

export function CalendarGrid() {
  const { calendarId } = useParams<{ calendarId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { addToast } = useToast();

  const [assignTarget, setAssignTarget] = useState<AssignTarget | null>(null);
  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null);
  const [generateSummary, setGenerateSummary] = useState<string | null>(null);
  const [assignmentWarning, setAssignmentWarning] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

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

  const { data: ranksData } = useQuery({
    queryKey: ["ranks"],
    queryFn: doctorsApi.listRanks,
    enabled: !!calendarId,
  });

  const doctorMap: Record<string, DoctorRead> = {};
  for (const d of doctorsData?.items ?? []) doctorMap[d.id] = d;

  const areaMap: Record<string, string> = {};
  for (const a of (serviceAreasData ?? []) as ServiceAreaRead[]) areaMap[a.id] = a.display_name;

  const rankMap: Record<string, RankRead> = {};
  for (const r of ranksData ?? []) rankMap[r.id] = r;

  const sortedAreaIds = [...(serviceAreasData ?? []) as ServiceAreaRead[]]
    .sort((a, b) => a.display_name.localeCompare(b.display_name))
    .map((a) => a.id);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });

  const approveMutation = useMutation({
    mutationFn: () => calendarsApi.approve(calendarId!),
    onSuccess: () => { invalidate(); addToast("success", "Calendario aprobado."); },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al aprobar."),
  });

  const unlockMutation = useMutation({
    mutationFn: () => calendarsApi.unlock(calendarId!),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Calendario desbloqueado. Ahora puedes editarlo.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al desbloquear calendario."),
  });

  const deleteCalendarMutation = useMutation({
    mutationFn: () => calendarsApi.delete(calendarId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Calendario eliminado.");
      navigate("/calendars");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al eliminar calendario."),
  });

  const generateMutation = useMutation({
    mutationFn: () => calendarsApi.generate(calendarId!),
    onSuccess: (result) => {
      invalidate();
      setGenerateSummary(`Asignados: ${result.assigned_count} / Huecos: ${result.gap_count} / Pendiente de aprobación`);
      addToast("success", result.review_required ? "Calendario generado y pendiente de revisión." : "Calendario generado.");
    },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al generar."),
  });

  const assignMutation = useMutation({
    mutationFn: ({ doctorId, overrideJustification }: AssignPayload) => {
      if (assignTarget?.currentAssignmentId) {
        return calendarsApi.replaceAssignment(calendarId!, data!.version.id, assignTarget.currentAssignmentId, doctorId, overrideJustification);
      }
      return calendarsApi.assignDoctor(calendarId!, data!.version.id, {
        service_date: assignTarget!.date,
        service_area_id: assignTarget!.areaId,
        doctor_id: doctorId,
        override_justification: overrideJustification ?? null,
      });
    },
    onSuccess: () => { invalidate(); setAssignTarget(null); setAssignmentWarning(null); addToast("success", "Médico asignado."); },
    onError: (err) => {
      if (
        err instanceof ApiError &&
        err.status === 422 &&
        err.detail &&
        typeof err.detail === "object" &&
        "code" in err.detail &&
        (err.detail as { code?: unknown }).code === "soft_warning"
      ) {
        setAssignmentWarning(err.message);
        return;
      }
      addToast("error", err instanceof ApiError ? err.message : "Error al asignar.");
    },
  });

  const removeMutation = useMutation({
    mutationFn: () => calendarsApi.removeAssignment(calendarId!, data!.version.id, removeTarget!.assignment.id),
    onSuccess: () => { invalidate(); setRemoveTarget(null); addToast("success", "Asignación quitada."); },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al quitar."),
  });

  const quickRemoveMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      calendarsApi.removeAssignment(calendarId!, data!.version.id, assignmentId),
    onSuccess: () => { invalidate(); setAssignTarget(null); setAssignmentWarning(null); addToast("success", "Asignación quitada."); },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al quitar."),
  });

  const { data: availableDoctorIds } = useQuery({
    queryKey: ["available-doctors", assignTarget?.date],
    queryFn: () => availabilityApi.availableDoctors(assignTarget!.date),
    enabled: !!assignTarget,
  });

  const { data: calendarWeeks = [] } = useQuery({
    queryKey: ["calendar-weeks", calendarId],
    queryFn: () => calendarsApi.listWeeks(calendarId!),
    enabled: !!calendarId,
  });

  const approveWeekMutation = useMutation({
    mutationFn: (weekId: string) => calendarsApi.approveWeek(calendarId!, weekId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendar-weeks", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Semana aprobada.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al aprobar semana."),
  });

  const unlockWeekMutation = useMutation({
    mutationFn: (weekId: string) => calendarsApi.unlockWeek(calendarId!, weekId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendar-weeks", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendars"] });
      addToast("success", "Semana desbloqueada.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al desbloquear semana."),
  });

  const handleExportWeeklyPDF = async (weekId: string) => {
    try {
      const blob = await calendarsApi.exportWeeklyPDF(calendarId!, weekId);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (err) {
      addToast("error", err instanceof ApiError ? err.message : "Error al exportar PDF semanal.");
    }
  };

  const handleExportFullCalendarPDF = async () => {
    try {
      const blob = await calendarsApi.exportFullCalendarPDF(calendarId!);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (err) {
      addToast("error", err instanceof ApiError ? err.message : "Error al exportar PDF del calendario.");
    }
  };

  if (!calendarId) return null;
  if (isLoading) return <p className="loading-text">Cargando grilla…</p>;
  if (error || !data) return <p className="error-text">Error al cargar el calendario.</p>;

  const { calendar, version, slots } = data;
  const isDraft = version.status === "draft";

  const calendarDays = buildCalendarDays(calendar.year, calendar.month);
  const weeks = chunkIntoWeeks(calendarDays);
  const isApproved = version.status === "approved";

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <button className="btn-ghost" onClick={() => navigate("/calendars")}>← Volver</button>
        <div style={{ display: "grid", gap: 3 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>
            Calendario {MONTHS[calendar.month - 1]} {calendar.year} — Versión {version.version_number}
          </h2>
          <span style={{ fontSize: 12, color: "#64748b" }}>
            {GENERATION_MODE_LABELS[calendar.generation_mode] ?? "Manual"}
          </span>
        </div>
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
              <Wand2 size={15} /> {generateMutation.isPending ? "Generando…" : "Generar con reglas"}
            </button>
            <button className="btn-primary" disabled={approveMutation.isPending} onClick={() => approveMutation.mutate()}>
              <CheckCircle2 size={16} /> {approveMutation.isPending ? "Aprobando…" : "Aprobar"}
            </button>
          </>
        )}
        {!isDraft && (
          <button className="btn-ghost" disabled={unlockMutation.isPending} onClick={() => unlockMutation.mutate()}>
            🔓 {unlockMutation.isPending ? "Desbloqueando…" : "Editar calendario"}
          </button>
        )}
        <button
          className="btn-ghost btn-danger"
          onClick={() => setShowDeleteDialog(true)}
          disabled={deleteCalendarMutation.isPending}
          title="Eliminar calendario"
        >
          <Trash2 size={15} />
        </button>
      </div>

      {generateSummary && (
        <p style={{ color: "#065f46", fontSize: 13, marginBottom: 8 }}>
          Generación con reglas completada — {generateSummary}
        </p>
      )}

      <div className="calendar-grid">
        {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => (
          <div key={d} className="calendar-grid-header">{d}</div>
        ))}
        {weeks.flat().map((cd, idx) => {
          if (cd.day === null || cd.dateStr === null) {
            return <div key={`pad-${idx}`} className="calendar-cell calendar-cell--outside" />;
          }
          const assignments = getDayAssignments(cd.dateStr, slots, areaMap, sortedAreaIds);
          return (
            <div key={cd.dateStr} className={`calendar-cell ${isApproved ? "calendar-cell--approved" : ""}`}>
              <span className="calendar-day-number">{cd.day}</span>
              {assignments.map((areaAss) => {
                const color = areaColor(areaAss.areaName);
                const doctor = areaAss.slot?.assignment ? doctorMap[areaAss.slot.assignment.doctor_id] : null;
                const rank = doctor?.rank_id ? rankMap[doctor.rank_id] : null;
                const handleAreaClick = () => {
                  if (!isDraft) return;
                  if (areaAss.slot?.assignment) {
                    setAssignTarget({
                      date: cd.dateStr!,
                      areaId: areaAss.areaId,
                      areaName: areaAss.areaName,
                      currentAssignmentId: areaAss.slot.assignment.id,
                      currentDoctorId: areaAss.slot.assignment.doctor_id,
                    });
                    setAssignmentWarning(null);
                  } else {
                    setAssignTarget({ date: cd.dateStr!, areaId: areaAss.areaId, areaName: areaAss.areaName });
                    setAssignmentWarning(null);
                  }
                };
                return (
                  <div key={areaAss.areaId} className={`calendar-area-row${isDraft ? " calendar-area-row--clickable" : ""}${!doctor && isDraft ? " calendar-area-row--empty" : ""}`}
                    role="button" tabIndex={0}
                    onClick={handleAreaClick}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleAreaClick(); } }}
                  >
                    <span className={`calendar-area-dot ${doctor ? "" : "calendar-area-dot--empty"}`} style={{ backgroundColor: color }} />
                    {doctor ? (
                      <span>{rank ? rankDisplayName(rank.name) + " " : ""}{doctor.name}</span>
                    ) : isDraft ? (
                      <span className="calendar-assign-label">+ Asignar médico</span>
                    ) : (
                      <span style={{ color: "#e2e8f0" }}>—</span>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {data.gaps.length > 0 && (
        <div style={{ marginTop: 12, padding: "10px 14px", background: "#fff7ed", borderRadius: 6, border: "1px solid #fed7aa" }}>
          <strong style={{ fontSize: 13 }}>Huecos sin resolver: {data.gaps.length}</strong>
        </div>
      )}

      {/* Week panel */}
      {calendarWeeks.length > 0 && (
        <div style={{ marginTop: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>Semanas</h3>
            <button
              className="btn-ghost"
              onClick={handleExportFullCalendarPDF}
              title="Exportar calendario completo en PDF"
            >
              <FileDown size={15} /> Calendario completo PDF
            </button>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e0e0e0", textAlign: "left" }}>
                <th style={{ padding: "0.4rem 0.5rem" }}>Semana</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Rango</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Asignaciones</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Estado</th>
                <th style={{ padding: "0.4rem 0.5rem" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {calendarWeeks.map((w: WeekRead) => (
                <tr key={w.id} style={{ borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: "0.4rem 0.5rem", fontWeight: 600 }}>
                    {w.label}
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem", color: "#555" }}>
                    {w.start_date} → {w.end_date}
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem" }}>
                    {w.assignment_count}
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem" }}>
                    <span style={{
                      display: "inline-block",
                      padding: "2px 8px",
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 700,
                      background: w.status === "approved" ? "#d1fae5" : "#f3f4f6",
                      color: w.status === "approved" ? "#065f46" : "#6b7280",
                    }}>
                      {w.status === "approved" ? "Aprobada" : "Borrador"}
                    </span>
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    {w.status === "draft" && isDraft && (
                      <button
                        className="btn-primary"
                        style={{ fontSize: 12, padding: "2px 10px" }}
                        disabled={approveWeekMutation.isPending}
                        onClick={() => approveWeekMutation.mutate(w.id)}
                      >
                        <CheckCircle2 size={13} /> Aprobar
                      </button>
                    )}
                    {w.status === "approved" && (
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 12, padding: "2px 10px" }}
                        disabled={unlockWeekMutation.isPending}
                        onClick={() => unlockWeekMutation.mutate(w.id)}
                      >
                        Desbloquear
                      </button>
                    )}
                    {w.status === "approved" && (
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 12, padding: "2px 10px" }}
                        onClick={() => handleExportWeeklyPDF(w.id)}
                        title="Exportar lista semanal en PDF"
                      >
                        <Download size={13} /> PDF
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {assignTarget && (
        <AssignDoctorModal
          date={assignTarget.date}
          areaName={assignTarget.areaName}
          doctors={doctorsData?.items ?? []}
          currentDoctorId={assignTarget.currentDoctorId}
          availableDoctorIds={availableDoctorIds}
          warningMessage={assignmentWarning}
          onConfirm={(doctorId, overrideJustification) => assignMutation.mutate({ doctorId, overrideJustification })}
          onClose={() => { setAssignTarget(null); setAssignmentWarning(null); }}
          isLoading={assignMutation.isPending}
          onRemove={assignTarget.currentAssignmentId ? () => quickRemoveMutation.mutate(assignTarget.currentAssignmentId!) : undefined}
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

      <ConfirmDialog
        open={showDeleteDialog}
        title="Eliminar calendario"
        message={`¿Estás seguro de eliminar ${MONTHS[calendar.month - 1]} ${calendar.year}?`}
        confirmLabel="Sí, eliminar"
        onConfirm={() => deleteCalendarMutation.mutate()}
        onCancel={() => setShowDeleteDialog(false)}
        isLoading={deleteCalendarMutation.isPending}
      />
    </div>
  );
}
