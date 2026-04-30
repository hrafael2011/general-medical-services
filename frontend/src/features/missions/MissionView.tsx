import { Target, PlusCircle, CheckCircle2, X, ChevronDown } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  missionsApi,
  MissionAssignment,
  MissionCandidateRankingEntry,
} from "../../api/missions";

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

// ---------------------------------------------------------------------------
// ConfirmModal
// ---------------------------------------------------------------------------

interface ConfirmModalProps {
  mission: MissionAssignment;
  onClose: () => void;
  onConfirmed: () => void;
}

function ConfirmModal({ mission, onClose, onConfirmed }: ConfirmModalProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const candidatesQuery = useQuery({
    queryKey: ["mission-candidates", mission.mission_date, mission.participant_count],
    queryFn: () =>
      missionsApi.getCandidates(mission.mission_date, mission.participant_count),
  });

  const confirmMutation = useMutation({
    mutationFn: () =>
      missionsApi.confirmMission(mission.id, Array.from(selectedIds)),
    onSuccess: onConfirmed,
  });

  function toggleDoctor(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const primary = candidatesQuery.data?.primary ?? [];

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

        {!candidatesQuery.isLoading && primary.length === 0 && (
          <p style={{ color: "#6b7280", marginBottom: 16 }}>Sin candidatos disponibles para esta fecha.</p>
        )}

        {primary.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ margin: "0 0 10px", fontSize: 13, color: "#374151", fontWeight: 600 }}>
              Candidatos primarios ({primary.length})
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 260, overflowY: "auto" }}>
              {primary.map((entry: MissionCandidateRankingEntry) => (
                <label
                  key={entry.id}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 12px", borderRadius: 8, cursor: "pointer",
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
                  <span style={{ flex: 1, fontSize: 14, fontFamily: "monospace" }}>
                    {entry.doctor_id}
                  </span>
                  <span style={{ fontSize: 12, color: "#6b7280" }}>
                    carga: {entry.total_load_score.toFixed(1)}
                  </span>
                  <span style={{ fontSize: 11, color: "#6b7280" }}>
                    pos. {entry.ranking_position}
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

        {confirmMutation.isError && (
          <p style={{ color: "#dc2626", marginTop: 10, fontSize: 13 }}>
            Error al confirmar mision.
          </p>
        )}
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
  const [date, setDate] = useState("");
  const [count, setCount] = useState(2);
  const [location, setLocation] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      missionsApi.createMission(date, count, location || undefined),
    onSuccess: onCreated,
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
      {createMutation.isError && (
        <p style={{ color: "#dc2626", marginTop: 8, fontSize: 13 }}>
          Error al crear la mision.
        </p>
      )}
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
  const [rankingLoaded, setRankingLoaded] = useState(false);

  // --- Missions section state ---
  const [showNewForm, setShowNewForm] = useState(false);
  const [confirmingMission, setConfirmingMission] = useState<MissionAssignment | null>(null);

  // --- Ranking query ---
  const rankingQuery = useQuery({
    queryKey: ["ranking", rankYear, rankMonth],
    queryFn: () => missionsApi.getRanking(rankYear, rankMonth),
    enabled: rankingLoaded,
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: () => missionsApi.generateRanking(rankYear, rankMonth),
    onSuccess: () => {
      setRankingLoaded(true);
      qc.invalidateQueries({ queryKey: ["ranking", rankYear, rankMonth] });
    },
  });

  // --- Missions query ---
  const missionsQuery = useQuery({
    queryKey: ["missions"],
    queryFn: () => missionsApi.listMissions(),
  });

  const ranking = rankingQuery.data;
  const entries = ranking?.entries ?? [];
  const missions = missionsQuery.data ?? [];

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
              onChange={e => { setRankYear(Number(e.target.value)); setRankingLoaded(false); }}
              style={{ width: 90, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14 }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
            Mes
            <select
              value={rankMonth}
              onChange={e => { setRankMonth(Number(e.target.value)); setRankingLoaded(false); }}
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
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            style={{
              padding: "7px 18px", borderRadius: 8, border: "none",
              background: "#0f172a", color: "#fff", cursor: "pointer",
              fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 6,
            }}
          >
            <ChevronDown size={15} />
            {generateMutation.isPending ? "Generando…" : "Generar ranking"}
          </button>
          {!rankingLoaded && (
            <button
              onClick={() => setRankingLoaded(true)}
              style={{
                padding: "7px 14px", borderRadius: 8,
                border: "1px solid #d1d5db", background: "#fff",
                cursor: "pointer", fontSize: 13, color: "#374151",
              }}
            >
              Ver existente
            </button>
          )}
        </div>

        {generateMutation.isError && (
          <p style={{ color: "#dc2626", marginBottom: 10, fontSize: 13 }}>
            Error al generar el ranking.
          </p>
        )}

        {rankingQuery.isLoading && (
          <p style={{ color: "#6b7280", fontSize: 13 }}>Cargando ranking…</p>
        )}

        {rankingQuery.isError && (
          <p style={{ color: "#6b7280", fontSize: 13 }}>Sin ranking generado para este periodo.</p>
        )}

        {ranking && entries.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pos.</th>
                  <th>Doctor ID</th>
                  <th>Carga total</th>
                  <th>Carga mensual</th>
                  <th>Elegible</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr key={entry.id}>
                    <td style={{ fontWeight: 700 }}>{entry.ranking_position}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 13 }}>{entry.doctor_id}</td>
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
