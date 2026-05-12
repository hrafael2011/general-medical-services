import { Target, PlusCircle, CheckCircle2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  missionsApi,
  MissionAssignment,
  MissionCandidateDateRankingEntry,
} from "../../api/missions";
import { doctorsApi } from "../../api/doctors";
import { ApiError } from "../../api/client";
import { useToast } from "../../components/Toast";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function currentYearMonth(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function statusBadge(status: string) {
  const style: React.CSSProperties =
    status === "confirmed"
      ? { background: "#d1fae5", color: "#065f46", borderRadius: 6, padding: "2px 10px", fontSize: 12, fontWeight: 600 }
      : { background: "#e5e7eb", color: "#374151", borderRadius: 6, padding: "2px 10px", fontSize: 12, fontWeight: 600 };
  return <span style={style}>{status === "confirmed" ? "Confirmada" : "Borrador"}</span>;
}

function candidateStatusLabel(status: MissionCandidateDateRankingEntry["recommendation_status"]) {
  if (status === "recommended") return "Recomendado";
  if (status === "alternate") return "Alterno";
  return "No seleccionable";
}

function candidateStatusStyle(status: MissionCandidateDateRankingEntry["recommendation_status"]): React.CSSProperties {
  if (status === "recommended") {
    return { background: "#d1fae5", color: "#065f46" };
  }
  if (status === "alternate") {
    return { background: "#fef3c7", color: "#92400e" };
  }
  return { background: "#fee2e2", color: "#991b1b" };
}

function doctorDisplayName(
  doctorId: string,
  doctorName: string | null | undefined,
  doctorNameById: Record<string, string>,
) {
  return doctorName?.trim() || doctorNameById[doctorId] || "Médico no encontrado";
}

// ---------------------------------------------------------------------------
// ConfirmModal
// ---------------------------------------------------------------------------

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
    queryFn: () =>
      missionsApi.getRankedCandidatesForDate(mission.mission_date),
  });

  const confirmMutation = useMutation({
    mutationFn: () =>
      missionsApi.confirmMission(mission.id, Array.from(selectedIds)),
    onSuccess: onConfirmed,
    onError: () => addToast("error", "Error al confirmar misión."),
  });

  function toggleDoctor(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const candidates = candidatesQuery.data?.entries ?? [];

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: "#fff", borderRadius: 12, padding: 28, width: 480,
          maxWidth: "90vw", boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 18 }}>Confirmar mision — {mission.mission_date}</h3>
          <button
            onClick={onClose}
            style={{ border: "none", background: "none", cursor: "pointer", padding: 4 }}
          >
            <X size={20} />
          </button>
        </div>

        {candidatesQuery.isLoading && (
          <p style={{ color: "#6b7280", marginBottom: 16 }}>Cargando candidatos…</p>
        )}

        {candidatesQuery.error && (
          <p style={{ color: "#dc2626", marginBottom: 16 }}>Error al cargar candidatos.</p>
        )}

        {!candidatesQuery.isLoading && candidates.length === 0 && (
          <p style={{ color: "#6b7280", marginBottom: 16 }}>Sin candidatos disponibles para esta fecha.</p>
        )}

        {candidates.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ margin: "0 0 10px", fontSize: 13, color: "#374151", fontWeight: 600 }}>
              Elegibles disponibles para la fecha ({candidates.length})
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 360, overflowY: "auto" }}>
              {candidates.map((entry: MissionCandidateDateRankingEntry) => (
                <label
                  key={entry.id}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 12px", borderRadius: 8,
                    cursor: "pointer",
                    background: selectedIds.has(entry.doctor_id) ? "#eff6ff" : "#f9fafb",
                    border: `1px solid ${selectedIds.has(entry.doctor_id) ? "#3b82f6" : "#e5e7eb"}`,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(entry.doctor_id)}
                    onChange={() => toggleDoctor(entry.doctor_id)}
                    style={{ accentColor: "#3b82f6" }}
                  />
                  <span style={{ width: 34, fontSize: 12, color: "#64748b", fontWeight: 700 }}>
                    #{entry.adjusted_position}
                  </span>
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
                  <span
                    style={{
                      ...candidateStatusStyle(entry.recommendation_status),
                      borderRadius: 999,
                      padding: "2px 8px",
                      fontSize: 11,
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {candidateStatusLabel(entry.recommendation_status)}
                  </span>
                  <span style={{ fontSize: 12, color: "#6b7280" }}>
                    carga: {entry.total_load_score.toFixed(1)}
                  </span>
                  <span style={{ fontSize: 11, color: "#6b7280" }}>
                    base {entry.ranking_position}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            onClick={onClose}
            style={{
              padding: "8px 18px", borderRadius: 8, border: "1px solid #e5e7eb",
              background: "#fff", cursor: "pointer", fontSize: 14,
            }}
          >
            Cancelar
          </button>
          <button
            onClick={() => confirmMutation.mutate()}
            disabled={selectedIds.size === 0 || confirmMutation.isPending}
            style={{
              padding: "8px 18px", borderRadius: 8, border: "none",
              background: selectedIds.size === 0 ? "#d1d5db" : "#2563eb",
              color: "#fff", cursor: selectedIds.size === 0 ? "not-allowed" : "pointer",
              fontSize: 14, fontWeight: 600,
            }}
          >
            <CheckCircle2 size={15} style={{ marginRight: 6, verticalAlign: "middle" }} />
            {confirmMutation.isPending ? "Confirmando…" : "Confirmar seleccion"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NewMissionForm
// ---------------------------------------------------------------------------

interface NewMissionFormProps {
  onCreated: () => void;
  onCancel: () => void;
}

function NewMissionForm({ onCreated, onCancel }: NewMissionFormProps) {
  const { addToast } = useToast();
  const [date, setDate] = useState("");
  const [count, setCount] = useState(2);
  const [location, setLocation] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      missionsApi.createMission(date, count, location || undefined),
    onSuccess: onCreated,
    onError: () => addToast("error", "Error al crear la misión."),
  });

  return (
    <div
      style={{
        background: "#f0f9ff", border: "1px solid #bae6fd",
        borderRadius: 10, padding: 20, marginBottom: 16,
      }}
    >
      <h4 style={{ margin: "0 0 14px", fontSize: 15, color: "#0369a1" }}>Nueva mision</h4>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          Fecha
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14 }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          Cantidad de medicos
          <input
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={e => setCount(Number(e.target.value))}
            style={{ width: 80, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14 }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          Lugar (opcional)
          <input
            type="text"
            value={location}
            onChange={e => setLocation(e.target.value)}
            placeholder="Ej: Base Norte"
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14, width: 180 }}
          />
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!date || createMutation.isPending}
            style={{
              padding: "7px 18px", borderRadius: 8, border: "none",
              background: !date ? "#d1d5db" : "#0369a1",
              color: "#fff", cursor: !date ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600,
            }}
          >
            {createMutation.isPending ? "Creando…" : "Crear"}
          </button>
          <button
            onClick={onCancel}
            style={{
              padding: "7px 14px", borderRadius: 8,
              border: "1px solid #bae6fd", background: "#fff", cursor: "pointer", fontSize: 14,
            }}
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MissionView
// ---------------------------------------------------------------------------

export function MissionView() {
  const qc = useQueryClient();
  const defaults = currentYearMonth();

  // --- Ranking section state ---
  const [rankYear, setRankYear] = useState(defaults.year);
  const [rankMonth, setRankMonth] = useState(defaults.month);

  // --- Missions section state ---
  const [showNewForm, setShowNewForm] = useState(false);
  const [confirmingMission, setConfirmingMission] = useState<MissionAssignment | null>(null);

  // --- Ranking query ---
  const rankingQuery = useQuery({
    queryKey: ["ranking", rankYear, rankMonth],
    queryFn: () => missionsApi.getRanking(rankYear, rankMonth),
    retry: false,
  });

  // --- Missions query ---
  const missionsQuery = useQuery({
    queryKey: ["missions"],
    queryFn: () => missionsApi.listMissions(),
  });

  const doctorsQuery = useQuery({
    queryKey: ["doctors", "mission-name-lookup"],
    queryFn: () => doctorsApi.list(false),
    staleTime: 5 * 60 * 1000,
  });

  const doctorNameById = useMemo(() => {
    const doctors = doctorsQuery.data?.items ?? [];
    return Object.fromEntries(doctors.map((doctor) => [doctor.id, doctor.name]));
  }, [doctorsQuery.data]);

  const ranking = rankingQuery.data;
  const entries = ranking?.entries ?? [];
  const missions = missionsQuery.data ?? [];
  const rankingErrorCode =
    rankingQuery.error instanceof ApiError &&
    rankingQuery.error.detail &&
    typeof rankingQuery.error.detail === "object"
      ? (rankingQuery.error.detail as { code?: string }).code
      : null;

  return (
    <div className="feature-panel">
      {/* ------------------------------------------------------------------ */}
      {/* Header                                                              */}
      {/* ------------------------------------------------------------------ */}
      <div className="feature-header">
        <div className="feature-title">
          <Target size={20} />
          <h2>Misiones</h2>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Ranking section                                                     */}
      {/* ------------------------------------------------------------------ */}
      <section style={{ marginBottom: 32 }}>
        <h3 style={{ fontSize: 16, marginBottom: 14, color: "#1e293b" }}>Ranking de candidatos</h3>

        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
            Ano
            <input
              type="number"
              value={rankYear}
              min={2020}
              max={2099}
              onChange={e => setRankYear(Number(e.target.value))}
              style={{ width: 90, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14 }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
            Mes
            <select
              value={rankMonth}
              onChange={e => setRankMonth(Number(e.target.value))}
              style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14 }}
            >
              {[
                "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
              ].map((name, i) => (
                <option key={i + 1} value={i + 1}>{name}</option>
              ))}
            </select>
          </label>
        </div>

        {rankingQuery.isLoading && (
          <p style={{ color: "#6b7280", fontSize: 13 }}>Cargando ranking…</p>
        )}

        {rankingQuery.isError && rankingErrorCode === "approved_calendar_required" && (
          <p style={{ color: "#92400e", fontSize: 13 }}>
            Este mes no tiene calendario aprobado. Aprueba el calendario para ver su ranking.
          </p>
        )}

        {rankingQuery.isError && rankingErrorCode !== "approved_calendar_required" && (
          <p style={{ color: "#6b7280", fontSize: 13 }}>
            Sin ranking generado para este periodo.
          </p>
        )}

        {ranking && entries.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pos.</th>
                  <th>Médico</th>
                  <th>Carga total</th>
                  <th>Carga mensual</th>
                  <th>Elegible</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr key={entry.id}>
                    <td style={{ fontWeight: 700 }}>{entry.ranking_position}</td>
                    <td>{doctorDisplayName(entry.doctor_id, entry.doctor_name, doctorNameById)}</td>
                    <td>{entry.total_load_score.toFixed(2)}</td>
                    <td>{entry.monthly_service_load.toFixed(2)}</td>
                    <td>
                      {entry.eligible
                        ? <span style={{ color: "#059669", fontWeight: 600 }}>Si</span>
                        : <span style={{ color: "#dc2626", fontWeight: 600 }}>No</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>
              Generado: {new Date(ranking.generated_at).toLocaleString()}
            </p>
          </div>
        )}

        {ranking && entries.length === 0 && (
          <p style={{ color: "#6b7280", fontSize: 13 }}>
            El ranking existe pero no tiene entradas para este periodo.
          </p>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Misiones section                                                    */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h3 style={{ fontSize: 16, margin: 0, color: "#1e293b" }}>Misiones</h3>
          <button
            className="btn-primary"
            onClick={() => setShowNewForm(v => !v)}
          >
            <PlusCircle size={15} />
            Nueva mision
          </button>
        </div>

        {showNewForm && (
          <NewMissionForm
            onCreated={() => {
              setShowNewForm(false);
              qc.invalidateQueries({ queryKey: ["missions"] });
            }}
            onCancel={() => setShowNewForm(false)}
          />
        )}

        {missionsQuery.isLoading && (
          <p className="loading-text">Cargando misiones…</p>
        )}

        {missionsQuery.isError && (
          <p className="error-text">Error al cargar misiones.</p>
        )}

        {!missionsQuery.isLoading && missions.length === 0 && (
          <p className="empty-text">No hay misiones registradas.</p>
        )}

        {missions.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Lugar</th>
                  <th>Cantidad</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {missions.map(mission => (
                  <tr key={mission.id}>
                    <td>{mission.mission_date}</td>
                    <td>{mission.location ?? <span style={{ color: "#9ca3af" }}>—</span>}</td>
                    <td>{mission.participant_count}</td>
                    <td>{statusBadge(mission.status)}</td>
                    <td className="cell-actions">
                      {mission.status === "draft" && (
                        <button
                          className="btn-ghost btn-green"
                          onClick={() => setConfirmingMission(mission)}
                        >
                          <CheckCircle2 size={14} />
                          Confirmar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Confirm modal                                                       */}
      {/* ------------------------------------------------------------------ */}
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
