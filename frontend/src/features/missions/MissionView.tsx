import { CheckCircle2, Edit3, PlusCircle, Target, Trash2, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  missionsApi,
  MissionAssignment,
  MissionCandidateDateRankingEntry,
} from "../../api/missions";
import { doctorsApi } from "../../api/doctors";
import { ApiError } from "../../api/client";
import { useToast } from "../../components/Toast";

type MissionSection = "manage" | "ranking";

function currentYearMonth(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function statusBadge(status: string) {
  const confirmed = status === "confirmed";
  return (
    <span style={{
      background: confirmed ? "#d1fae5" : "#e5e7eb",
      color: confirmed ? "#065f46" : "#374151",
      borderRadius: 6,
      padding: "2px 10px",
      fontSize: 12,
      fontWeight: 600,
    }}>
      {confirmed ? "Confirmada" : "Borrador"}
    </span>
  );
}

function candidateStatusLabel(status: MissionCandidateDateRankingEntry["recommendation_status"]) {
  if (status === "recommended") return "Recomendado";
  if (status === "alternate") return "Alterno";
  return "No seleccionable";
}

function candidateStatusStyle(status: MissionCandidateDateRankingEntry["recommendation_status"]): React.CSSProperties {
  if (status === "recommended") return { background: "#d1fae5", color: "#065f46" };
  if (status === "alternate") return { background: "#fef3c7", color: "#92400e" };
  return { background: "#fee2e2", color: "#991b1b" };
}

function doctorDisplayName(
  doctorId: string,
  doctorName: string | null | undefined,
  doctorNameById: Record<string, string>,
) {
  return doctorName?.trim() || doctorNameById[doctorId] || "Médico no encontrado";
}

interface MissionFormProps {
  mission?: MissionAssignment;
  onCancel?: () => void;
  onSaved: () => void;
}

function MissionForm({ mission, onCancel, onSaved }: MissionFormProps) {
  const { addToast } = useToast();
  const [date, setDate] = useState(mission?.mission_date ?? "");
  const [count, setCount] = useState(mission?.participant_count ?? 2);
  const [location, setLocation] = useState(mission?.location ?? "");
  const [description, setDescription] = useState(mission?.description ?? "");
  const isEditing = Boolean(mission);

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        mission_date: date,
        participant_count: count,
        location: location.trim() || null,
        description: description.trim() || null,
      };
      return mission
        ? missionsApi.updateMission(mission.id, payload)
        : missionsApi.createMission(date, count, location || undefined, description || undefined);
    },
    onSuccess: onSaved,
    onError: () => addToast("error", isEditing ? "Error al editar la misión." : "Error al crear la misión."),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!date || count < 1) return;
    mutation.mutate();
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        background: "#f8fafc",
        border: "1px solid #e2e8f0",
        borderRadius: 8,
        padding: 18,
        marginBottom: 16,
      }}
    >
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          Fecha
          <input type="date" value={date} onChange={e => setDate(e.target.value)} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          Cantidad de médicos
          <input type="number" min={1} max={20} value={count} onChange={e => setCount(Number(e.target.value))} style={{ width: 100 }} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          Lugar
          <input type="text" value={location} onChange={e => setLocation(e.target.value)} placeholder="Ej: Base Norte" />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, flex: "1 1 220px" }}>
          Descripción
          <input type="text" value={description} onChange={e => setDescription(e.target.value)} />
        </label>
        <button className="btn-primary" type="submit" disabled={!date || mutation.isPending}>
          {isEditing ? <Edit3 size={15} /> : <PlusCircle size={15} />}
          {mutation.isPending ? "Guardando…" : isEditing ? "Guardar" : "Crear"}
        </button>
        {onCancel && (
          <button className="btn-ghost" type="button" onClick={onCancel}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

interface ConfirmModalProps {
  mission: MissionAssignment;
  doctorNameById: Record<string, string>;
  onClose: () => void;
  onConfirmed: () => void;
}

function ConfirmModal({ mission, doctorNameById, onClose, onConfirmed }: ConfirmModalProps) {
  const { addToast } = useToast();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const candidatesQuery = useQuery({
    queryKey: ["mission-candidates-ranked", mission.mission_date],
    queryFn: () => missionsApi.getRankedCandidatesForDate(mission.mission_date),
  });
  const confirmMutation = useMutation({
    mutationFn: () => missionsApi.confirmMission(mission.id, Array.from(selectedIds)),
    onSuccess: onConfirmed,
    onError: () => addToast("error", "Error al confirmar misión."),
  });
  const candidates = candidatesQuery.data?.entries ?? [];

  function toggleDoctor(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ background: "#fff", borderRadius: 8, padding: 24, width: 560, maxWidth: "92vw", boxShadow: "0 8px 32px rgba(0,0,0,0.18)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 18 }}>Confirmar misión - {mission.mission_date}</h3>
          <button onClick={onClose} style={{ border: "none", background: "none", cursor: "pointer", padding: 4 }} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>

        {candidatesQuery.isLoading && <p style={{ color: "#6b7280" }}>Cargando candidatos…</p>}
        {candidatesQuery.error && <p style={{ color: "#dc2626" }}>Error al cargar candidatos.</p>}
        {!candidatesQuery.isLoading && candidates.length === 0 && <p style={{ color: "#6b7280" }}>Sin candidatos disponibles para esta fecha.</p>}

        {candidates.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ margin: "0 0 10px", fontSize: 13, color: "#374151", fontWeight: 600 }}>
              Elegibles disponibles para la fecha ({candidates.length})
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 360, overflowY: "auto" }}>
              {candidates.map(entry => (
                <label key={entry.id} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderRadius: 8,
                  cursor: "pointer", background: selectedIds.has(entry.doctor_id) ? "#eff6ff" : "#f9fafb",
                  border: `1px solid ${selectedIds.has(entry.doctor_id) ? "#3b82f6" : "#e5e7eb"}`,
                }}>
                  <input type="checkbox" checked={selectedIds.has(entry.doctor_id)} onChange={() => toggleDoctor(entry.doctor_id)} />
                  <span style={{ width: 34, fontSize: 12, color: "#64748b", fontWeight: 700 }}>#{entry.adjusted_position}</span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: 14, fontWeight: 600 }}>
                      {doctorDisplayName(entry.doctor_id, entry.doctor_name, doctorNameById)}
                    </span>
                    {(entry.reasons.length > 0 || entry.warnings.length > 0) && (
                      <span style={{ display: "block", fontSize: 11, color: "#64748b", marginTop: 2 }}>
                        {[...entry.reasons, ...entry.warnings].join(" ")}
                      </span>
                    )}
                  </span>
                  <span style={{ ...candidateStatusStyle(entry.recommendation_status), borderRadius: 999, padding: "2px 8px", fontSize: 11, fontWeight: 700, whiteSpace: "nowrap" }}>
                    {candidateStatusLabel(entry.recommendation_status)}
                  </span>
                  <span style={{ fontSize: 12, color: "#6b7280" }}>carga: {entry.total_load_score.toFixed(1)}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn-primary" onClick={() => confirmMutation.mutate()} disabled={selectedIds.size === 0 || confirmMutation.isPending}>
            <CheckCircle2 size={15} />
            {confirmMutation.isPending ? "Confirmando…" : "Confirmar selección"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function MissionView() {
  const qc = useQueryClient();
  const { addToast } = useToast();
  const defaults = currentYearMonth();
  const [section, setSection] = useState<MissionSection>("manage");
  const [rankYear, setRankYear] = useState(defaults.year);
  const [rankMonth, setRankMonth] = useState(defaults.month);
  const [editingMission, setEditingMission] = useState<MissionAssignment | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [confirmingMission, setConfirmingMission] = useState<MissionAssignment | null>(null);

  const rankingQuery = useQuery({
    queryKey: ["ranking", rankYear, rankMonth],
    queryFn: () => missionsApi.getRanking(rankYear, rankMonth),
    retry: false,
  });
  const missionsQuery = useQuery({
    queryKey: ["missions"],
    queryFn: () => missionsApi.listMissions(),
  });
  const doctorsQuery = useQuery({
    queryKey: ["doctors", "mission-name-lookup"],
    queryFn: () => doctorsApi.list(false),
    staleTime: 5 * 60 * 1000,
  });
  const deleteMutation = useMutation({
    mutationFn: (missionId: string) => missionsApi.deleteMission(missionId),
    onSuccess: () => {
      addToast("success", "Misión eliminada.");
      qc.invalidateQueries({ queryKey: ["missions"] });
    },
    onError: () => addToast("error", "Error al eliminar la misión."),
  });

  const doctorNameById = useMemo(() => {
    const doctors = doctorsQuery.data?.items ?? [];
    return Object.fromEntries(doctors.map(doctor => [doctor.id, doctor.name]));
  }, [doctorsQuery.data]);

  const missions = missionsQuery.data ?? [];
  const ranking = rankingQuery.data;
  const entries = ranking?.entries ?? [];
  const rankingErrorCode =
    rankingQuery.error instanceof ApiError &&
    rankingQuery.error.detail &&
    typeof rankingQuery.error.detail === "object"
      ? (rankingQuery.error.detail as { code?: string }).code
      : null;

  function refreshMissions() {
    setEditingMission(null);
    setShowCreateForm(false);
    setSection("manage");
    qc.invalidateQueries({ queryKey: ["missions"] });
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <Target size={20} />
          <h2>Misiones</h2>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 22, flexWrap: "wrap" }}>
        {[
          ["manage", "Gestión de misiones"],
          ["ranking", "Ranking de candidatos"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={section === key ? "btn-primary" : "btn-ghost"}
            onClick={() => setSection(key as MissionSection)}
          >
            {label}
          </button>
        ))}
      </div>

      {section === "ranking" && (
        <section>
          <h3 style={{ fontSize: 16, marginBottom: 14, color: "#1e293b" }}>Ranking de candidatos</h3>
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Año
              <input type="number" value={rankYear} min={2020} max={2099} onChange={e => setRankYear(Number(e.target.value))} style={{ width: 90 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Mes
              <select value={rankMonth} onChange={e => setRankMonth(Number(e.target.value))}>
                {["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].map((name, i) => (
                  <option key={i + 1} value={i + 1}>{name}</option>
                ))}
              </select>
            </label>
          </div>
          {rankingQuery.isLoading && <p style={{ color: "#6b7280", fontSize: 13 }}>Cargando ranking…</p>}
          {rankingQuery.isError && rankingErrorCode === "approved_calendar_required" && (
            <p style={{ color: "#92400e", fontSize: 13 }}>Este mes no tiene semanas aprobadas. Aprueba al menos una semana para ver el ranking.</p>
          )}
          {rankingQuery.isError && rankingErrorCode !== "approved_calendar_required" && (
            <p style={{ color: "#6b7280", fontSize: 13 }}>Sin ranking generado para este periodo.</p>
          )}
          {ranking && entries.length > 0 && (
            <div className="table-wrapper">
              <details style={{ marginBottom: 10, fontSize: 12, color: "#6b7280" }}>
                <summary style={{ cursor: "pointer", fontWeight: 500 }}>
                  ¿Cómo se calcula la puntuación?
                </summary>
                <ul style={{ marginTop: 6, paddingLeft: 16, lineHeight: 1.6 }}>
                  <li><strong>Pesos por área:</strong> Emergencia = 3, Pista = 2, Disponible = 1.</li>
                  <li><strong>Carga mensual:</strong> Suma de los pesos de las áreas asignadas en el mes. No es cantidad de servicios.</li>
                  <li><strong>Carga total:</strong> Carga mensual + 50% de carga de últimos 60 días + 0.5 por cada misión del mes.</li>
                  <li><strong>Posición:</strong> Orden de menor a mayor carga total. Menor carga = mayor prioridad.</li>
                </ul>
              </details>
              <table className="data-table">
                <thead>
                  <tr><th>Pos.</th><th>Médico</th><th>Carga total</th><th>Carga mensual</th><th>Elegible</th></tr>
                </thead>
                <tbody>
                  {entries.map(entry => (
                    <tr key={entry.id}>
                      <td style={{ fontWeight: 700 }}>{entry.ranking_position}</td>
                      <td>{doctorDisplayName(entry.doctor_id, entry.doctor_name, doctorNameById)}</td>
                      <td>{entry.total_load_score.toFixed(2)}</td>
                      <td>{entry.monthly_service_load.toFixed(2)}</td>
                      <td>{entry.eligible ? <span style={{ color: "#059669", fontWeight: 600 }}>Sí</span> : <span style={{ color: "#dc2626", fontWeight: 600 }}>No</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>Generado: {new Date(ranking.generated_at).toLocaleString()}</p>
            </div>
          )}
          {ranking && entries.length === 0 && <p style={{ color: "#6b7280", fontSize: 13 }}>El ranking existe pero no tiene entradas para este periodo.</p>}
        </section>
      )}

      {section === "manage" && (
        <section>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
            <h3 style={{ fontSize: 16, margin: 0, color: "#1e293b" }}>Gestión de misiones</h3>
            <button
              className={showCreateForm ? "btn-ghost" : "btn-primary"}
              onClick={() => {
                setShowCreateForm(prev => !prev);
                setEditingMission(null);
              }}
            >
              <PlusCircle size={15} />
              {showCreateForm ? "Ocultar creación" : "Crear misión"}
            </button>
          </div>
          {showCreateForm && (
            <MissionForm onSaved={refreshMissions} onCancel={() => setShowCreateForm(false)} />
          )}
          {editingMission && (
            <MissionForm mission={editingMission} onSaved={refreshMissions} onCancel={() => setEditingMission(null)} />
          )}
          {missionsQuery.isLoading && <p className="loading-text">Cargando misiones…</p>}
          {missionsQuery.isError && <p className="error-text">Error al cargar misiones.</p>}
          {!missionsQuery.isLoading && missions.length === 0 && <p className="empty-text">No hay misiones registradas.</p>}
          {missions.length > 0 && (
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr><th>Fecha</th><th>Lugar</th><th>Cantidad</th><th>Estado</th><th>Participantes</th><th></th></tr>
                </thead>
                <tbody>
                  {missions.map(mission => (
                    <tr key={mission.id}>
                      <td>{mission.mission_date}</td>
                      <td>{mission.location ?? <span style={{ color: "#9ca3af" }}>—</span>}</td>
                      <td>{mission.participant_count}</td>
                      <td>
                        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                          {statusBadge(mission.status)}
                          {mission.has_replacement_warnings && (
                            <span className="warning-badge">
                              {mission.replacement_warning_count} reemplazo pendiente
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "grid", gap: 4 }}>
                          <span>{mission.participants.length}</span>
                          {mission.participants
                            .filter(participant => participant.requires_replacement)
                            .map(participant => (
                              <span key={participant.id} className="mission-replacement-warning">
                                {participant.doctor_name ?? "Médico no encontrado"}: {participant.replacement_reason}
                              </span>
                            ))}
                        </div>
                      </td>
                      <td className="cell-actions">
                        {mission.status === "draft" && (
                          <button className="btn-ghost btn-green" onClick={() => setConfirmingMission(mission)}>
                            <CheckCircle2 size={14} />
                            Confirmar
                          </button>
                        )}
                        <button className="btn-ghost" onClick={() => setEditingMission(mission)} aria-label={`Editar misión ${mission.mission_date}`}>
                          <Edit3 size={14} />
                          Editar
                        </button>
                        <button
                          className="btn-ghost btn-danger"
                          onClick={() => {
                            if (window.confirm("¿Eliminar esta misión?")) deleteMutation.mutate(mission.id);
                          }}
                          aria-label={`Eliminar misión ${mission.mission_date}`}
                        >
                          <Trash2 size={14} />
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {confirmingMission && (
        <ConfirmModal
          mission={confirmingMission}
          doctorNameById={doctorNameById}
          onClose={() => setConfirmingMission(null)}
          onConfirmed={() => {
            setConfirmingMission(null);
            qc.invalidateQueries({ queryKey: ["missions"] });
          }}
        />
      )}
    </div>
  );
}
