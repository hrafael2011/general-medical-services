// frontend/src/features/calendars/CalendarGrid.tsx
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { calendarsApi, CalendarAssignmentRead, DaySlot } from "../../api/calendars";
import { doctorsApi, DoctorRead, RankRead } from "../../api/doctors";
import type { ServiceAreaRead } from "../../api/doctors";
import { AssignDoctorModal } from "./AssignDoctorModal";
import { RemoveAssignmentPopover } from "./RemoveAssignmentPopover";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";

const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

interface AssignTarget { date: string; areaId: string; areaName: string; }
interface RemoveTarget { assignment: CalendarAssignmentRead; areaName: string; }

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

  const calendarDays = buildCalendarDays(calendar.year, calendar.month);
  const weeks = chunkIntoWeeks(calendarDays);
  const isApproved = version.status === "approved";

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
              {assignments.map((areaAss, ai) => {
                const color = areaColor(areaAss.areaName);
                const doctor = areaAss.slot?.assignment ? doctorMap[areaAss.slot.assignment.doctor_id] : null;
                const rank = doctor?.rank_id ? rankMap[doctor.rank_id] : null;
                const handleAreaClick = () => {
                  if (!isDraft) return;
                  if (areaAss.slot?.assignment) {
                    setRemoveTarget({ assignment: areaAss.slot.assignment, areaName: areaAss.areaName });
                  } else {
                    setAssignTarget({ date: cd.dateStr!, areaId: areaAss.areaId, areaName: areaAss.areaName });
                  }
                };
                return (
                  <div key={areaAss.areaId} className={`calendar-area-row${isDraft ? " calendar-area-row--clickable" : ""}`}
                    role="button" tabIndex={0}
                    onClick={handleAreaClick}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleAreaClick(); } }}
                  >
                    <span className={`calendar-area-dot ${doctor ? "" : "calendar-area-dot--empty"}`} style={{ backgroundColor: color }} />
                    {doctor ? (
                      <span>{rank ? rankDisplayName(rank.name) + " " : ""}{doctor.name}</span>
                    ) : isDraft ? (
                      <span style={{ color: "#cbd5e1" }}>— — —</span>
                    ) : (
                      <span style={{ color: "#e2e8f0" }}>—</span>
                    )}
                  </div>
                );
              })}
              {isDraft && (
                <div className="calendar-assign-link" role="button" tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    const firstEmpty = assignments.find((a) => !a.slot?.assignment);
                    if (firstEmpty) setAssignTarget({ date: cd.dateStr!, areaId: firstEmpty.areaId, areaName: firstEmpty.areaName });
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      e.stopPropagation();
                      const firstEmpty = assignments.find((a) => !a.slot?.assignment);
                      if (firstEmpty) setAssignTarget({ date: cd.dateStr!, areaId: firstEmpty.areaId, areaName: firstEmpty.areaName });
                    }
                  }}
                >+ Asignar</div>
              )}
            </div>
          );
        })}
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
