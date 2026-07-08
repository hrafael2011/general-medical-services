// frontend/src/features/calendars/CalendarGrid.tsx
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileDown, Loader2, Trash2, Wand2 } from "lucide-react";
import { calendarsApi, CalendarAssignmentRead, DaySlot, WeekRead } from "../../api/calendars";
import { doctorsApi, DoctorRead, RankRead } from "../../api/doctors";
import type { ServiceAreaRead } from "../../api/doctors";
import { AssignDoctorModal } from "./AssignDoctorModal";
import { RemoveAssignmentPopover } from "./RemoveAssignmentPopover";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";

const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
const MONTHS_SHORT = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

const GENERATION_MODE_LABELS = {
  manual: "Manual",
  assisted_auto: "Generado con reglas",
  scheduled_auto: "Auto programado",
} as const;

interface AssignTarget { date: string; areaId: string; areaName: string; currentAssignmentId?: string; currentDoctorId?: string; }
interface RemoveTarget { assignment: CalendarAssignmentRead; areaName: string; }

interface CalendarDay {
  day: number;
  month: number;
  dateStr: string;
  isCurrentMonth: boolean;
}

/** Same logic as backend compute_weeks: every week is Monday-Sunday, and a
 *  week belongs to the month where its Monday falls. */
function buildCalendarDays(year: number, month: number): CalendarDay[] {
  const firstDay = new Date(year, month - 1, 1);
  const days: CalendarDay[] = [];

  // Find the first Monday in the month.
  // getDay(): 0=Sunday, 1=Monday, ..., 6=Saturday.
  const daysUntilMonday = (8 - firstDay.getDay()) % 7;
  const currentMonday = new Date(firstDay);
  currentMonday.setDate(firstDay.getDate() + daysUntilMonday);

  while (currentMonday.getMonth() + 1 === month) {
    for (let i = 0; i < 7; i++) {
      const d = new Date(currentMonday);
      d.setDate(currentMonday.getDate() + i);
      const m = d.getMonth() + 1;
      days.push({
        day: d.getDate(),
        month: m,
        dateStr: `${d.getFullYear()}-${String(m).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`,
        isCurrentMonth: m === month,
      });
    }
    currentMonday.setDate(currentMonday.getDate() + 7);
  }

  return days;
}

function dayLabel(cd: CalendarDay): string {
  if (cd.isCurrentMonth) return String(cd.day);
  return `${MONTHS_SHORT[cd.month - 1]} ${cd.day}`;
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

function findWeekForDate(dateStr: string, weeks: WeekRead[]): WeekRead | null {
  return weeks.find((week) => week.start_date <= dateStr && dateStr <= week.end_date) ?? null;
}

function rankDisplayName(rankName: string): string {
  return rankName.toUpperCase();
}

function matchesHighlight(name: string, term: string): boolean {
  if (!term || term.length < 2) return false;
  return name.toLowerCase().includes(term.toLowerCase());
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
  const [highlightTerm, setHighlightTerm] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["calendar-grid", calendarId],
    queryFn: () => calendarsApi.getGrid(calendarId!),
    enabled: !!calendarId,
  });

  const { data: doctorsData } = useQuery({
    queryKey: ["doctors", "all"],
    queryFn: () => doctorsApi.list("all"),
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
    .sort((a, b) => {
      const order = ["Emergencia", "Pista", "Disponible"];
      return order.indexOf(a.display_name) - order.indexOf(b.display_name);
    })
    .map((a) => a.id);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["calendar-grid", calendarId] });

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
      qc.invalidateQueries({ queryKey: ["calendar-weeks", calendarId] });
      qc.invalidateQueries({ queryKey: ["calendars"] });
      setGenerateSummary(`Asignados: ${result.assigned_count} / Huecos: ${result.gap_count} / Pendiente de aprobación`);
      addToast("success", result.review_required ? "Calendario generado y pendiente de revisión." : "Calendario generado.");
    },
    onError: (err) => addToast("error", err instanceof ApiError ? err.message : "Error al generar."),
  });

  const assignMutation = useMutation({
    mutationFn: ({ doctorId, forceWarnings }: { doctorId: string; forceWarnings: string[] }) => {
      if (!assignTarget) throw new Error("Missing data");
      if (assignTarget.currentAssignmentId) {
        return calendarsApi.replaceAssignment(
          calendarId!, data!.version.id, assignTarget.currentAssignmentId, doctorId, null, forceWarnings.length > 0 ? forceWarnings : null
        );
      }
      return calendarsApi.assignDoctor(calendarId!, data!.version.id, {
        service_date: assignTarget.date,
        service_area_id: assignTarget.areaId,
        doctor_id: doctorId,
        force_warnings: forceWarnings.length > 0 ? forceWarnings : null,
      });
    },
    onSuccess: () => {
      invalidate();
      setAssignTarget(null);
      setAssignmentWarning(null);
      addToast("success", "Médico asignado.");
    },
    onError: (err: unknown) => {
      setAssignmentWarning(
        err instanceof ApiError ? err.message : "Error al asignar doctor."
      );
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

  const exportWeekPdfMutation = useMutation({
    mutationFn: (weekId: string) => calendarsApi.exportWeeklyPDF(calendarId!, weekId),
    onSuccess: (blob) => {
      window.open(URL.createObjectURL(blob), "_blank");
      addToast("success", "PDF semanal exportado.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al exportar PDF semanal."),
  });

  const exportFullCalendarPdfMutation = useMutation({
    mutationFn: () => calendarsApi.exportFullCalendarPDF(calendarId!),
    onSuccess: (blob) => {
      window.open(URL.createObjectURL(blob), "_blank");
      addToast("success", "PDF del calendario exportado.");
    },
    onError: (err) =>
      addToast("error", err instanceof ApiError ? err.message : "Error al exportar PDF del calendario."),
  });

  if (!calendarId) return null;
  if (isLoading) return <p className="loading-text">Cargando grilla…</p>;
  if (error || !data) return <p className="error-text">Error al cargar el calendario.</p>;

  const { calendar, version, slots } = data;
  const isDraft = version.status === "draft";
  const hasApprovedWeeks = calendarWeeks.some((week) => week.status === "approved");
  const calendarStatusLabel = calendar.status === "approved"
    ? "Aprobado"
    : calendar.status === "partial"
      ? "Parcial"
      : "Borrador";
  const calendarStatusStyle = calendar.status === "approved"
    ? { background: "#d1fae5", color: "#065f46" }
    : calendar.status === "partial"
      ? { background: "#fef3c7", color: "#92400e" }
      : { background: "#f3f4f6", color: "#6b7280" };

  const calendarDays = buildCalendarDays(calendar.year, calendar.month);
  const weeks = chunkIntoWeeks(calendarDays);
  const isApproved = calendar.status === "approved" || version.status === "approved";

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
          ...calendarStatusStyle,
        }}>
          {calendarStatusLabel}
        </span>
        {isDraft && !hasApprovedWeeks && slots.length === 0 && (
          <>
            <button className="btn-ghost" disabled={generateMutation.isPending} onClick={() => generateMutation.mutate()}>
              <Wand2 size={15} /> {generateMutation.isPending ? "Generando…" : "Generar calendario con reglas"}
            </button>
          </>
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
          Calendario creado con reglas — {generateSummary}
        </p>
      )}

      {/* Buscador de médicos */}
      <div style={{ marginBottom: "0.5rem" }}>
        <input
          type="text"
          value={highlightTerm}
          onChange={(e) => setHighlightTerm(e.target.value)}
          placeholder="Buscar médico en la grilla..."
          style={{
            padding: "6px 10px", fontSize: 13, border: "1px solid #cbd5e1",
            borderRadius: 6, width: 260, outline: "none",
          }}
        />
        {highlightTerm.length >= 2 && (
          (() => {
            const hasMatch = Object.values(doctorMap).some(d =>
              matchesHighlight(d.name, highlightTerm)
            );
            if (!hasMatch) {
              return (
                <span style={{ marginLeft: 12, fontSize: 12, color: "#94a3b8" }}>
                  No se encontraron médicos con ese nombre
                </span>
              );
            }
            return null;
          })()
        )}
      </div>

      {/* Leyenda de áreas */}
      <div style={{ display: "flex", gap: "1rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
        {sortedAreaIds.map((areaId) => {
          const areaName = areaMap[areaId] ?? areaId;
          const color = areaColor(areaName);
          return (
            <span key={areaId} style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: color, display: "inline-block" }} />
              {areaName}
            </span>
          );
        })}
      </div>

      <div className="calendar-grid">
        {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => (
          <div key={d} className="calendar-grid-header">{d}</div>
        ))}
        {weeks.flat().map((cd) => {
          const assignments = getDayAssignments(cd.dateStr, slots, areaMap, sortedAreaIds);
          if (!cd.isCurrentMonth) {
            return (
              <div key={cd.dateStr} className="calendar-cell calendar-cell--outside">
                <span className="calendar-day-number calendar-day-number--outside">{dayLabel(cd)}</span>
                {assignments.map((areaAss) => {
                  const color = areaColor(areaAss.areaName);
                  const doctor = areaAss.slot?.assignment ? doctorMap[areaAss.slot.assignment.doctor_id] : null;
                  const rank = doctor?.rank_id ? rankMap[doctor.rank_id] : null;
                  const isEditableSlot = isDraft;
                  const hl = doctor && matchesHighlight(doctor.name, highlightTerm);
                  const handleAreaClick = () => {
                    if (!isEditableSlot) return;
                    if (areaAss.slot?.assignment) {
                      setAssignTarget({ date: cd.dateStr, areaId: areaAss.areaId, areaName: areaAss.areaName, currentAssignmentId: areaAss.slot.assignment.id, currentDoctorId: areaAss.slot.assignment.doctor_id });
                    } else {
                      setAssignTarget({ date: cd.dateStr, areaId: areaAss.areaId, areaName: areaAss.areaName });
                    }
                    setAssignmentWarning(null);
                  };
                  return (
                    <div key={areaAss.areaId}
                      className={`calendar-area-row${isEditableSlot ? " calendar-area-row--clickable" : ""}${!doctor && isEditableSlot ? " calendar-area-row--empty" : ""}${hl ? " calendar-cell--highlight" : ""}`}
                      role="button" tabIndex={0}
                      onClick={handleAreaClick}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleAreaClick(); } }}
                    >
                      <span className={`calendar-area-dot ${doctor ? "" : "calendar-area-dot--empty"}`} style={{ backgroundColor: color }} />
                      {doctor ? (
                        <span>{rank ? rankDisplayName(rank.name) + " " : ""}{doctor.name}</span>
                      ) : isEditableSlot ? (
                        <span className="calendar-assign-label">+ Asignar médico</span>
                      ) : (
                        <span style={{ color: "#e2e8f0" }}>—</span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          }
          return (
            <div
              key={cd.dateStr}
              className={`calendar-cell ${isApproved ? "calendar-cell--approved" : ""} ${findWeekForDate(cd.dateStr, calendarWeeks)?.status === "approved" ? "calendar-cell--approved-week" : ""}`}
            >
              <span className="calendar-day-number">{dayLabel(cd)}</span>
              {assignments.map((areaAss) => {
                const color = areaColor(areaAss.areaName);
                const doctor = areaAss.slot?.assignment ? doctorMap[areaAss.slot.assignment.doctor_id] : null;
                const rank = doctor?.rank_id ? rankMap[doctor.rank_id] : null;
                const hl = doctor && matchesHighlight(doctor.name, highlightTerm);
                const week = findWeekForDate(cd.dateStr, calendarWeeks);
                const isEditableSlot = isDraft && week?.status !== "approved";
                const handleAreaClick = () => {
                  if (!isEditableSlot) return;
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
                  <div key={areaAss.areaId} className={`calendar-area-row${isEditableSlot ? " calendar-area-row--clickable" : ""}${!doctor && isEditableSlot ? " calendar-area-row--empty" : ""}${hl ? " calendar-cell--highlight" : ""}`}
                    role="button" tabIndex={0}
                    onClick={handleAreaClick}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleAreaClick(); } }}
                  >
                    <span className={`calendar-area-dot ${doctor ? "" : "calendar-area-dot--empty"}`} style={{ backgroundColor: color }} />
                    {doctor ? (
                      <span>{rank ? rankDisplayName(rank.name) + " " : ""}{doctor.name}</span>
                    ) : isEditableSlot ? (
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
              disabled={exportFullCalendarPdfMutation.isPending}
              onClick={() => exportFullCalendarPdfMutation.mutate()}
              title="Exportar calendario completo en PDF"
            >
              {exportFullCalendarPdfMutation.isPending ? <Loader2 size={15} className="spin" /> : <FileDown size={15} />}
              {exportFullCalendarPdfMutation.isPending ? "Exportando…" : "Calendario completo PDF"}
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
                        disabled={exportWeekPdfMutation.isPending}
                        onClick={() => exportWeekPdfMutation.mutate(w.id)}
                        title="Exportar lista semanal en PDF"
                      >
                        {exportWeekPdfMutation.isPending ? <Loader2 size={13} className="spin" /> : <Download size={13} />}
                        {exportWeekPdfMutation.isPending ? "Exportando…" : "PDF"}
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
          calendarId={calendarId!}
          versionId={data!.version.id}
          date={assignTarget.date}
          areaId={assignTarget.areaId}
          areaName={assignTarget.areaName}
          currentDoctorId={assignTarget.currentDoctorId}
          currentAssignmentId={assignTarget.currentAssignmentId}
          onConfirm={(doctorId, forceWarnings) => assignMutation.mutate({ doctorId, forceWarnings })}
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
