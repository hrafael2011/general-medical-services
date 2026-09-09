import { useState, useEffect } from "react";
import { Search, AlertTriangle, CheckCircle2, Lock } from "lucide-react";
import { EligibleDoctorRead, UnavailableDoctorRead, WarningItem, calendarsApi } from "../../api/calendars";
import { ApiError } from "../../api/client";

const MONTHS = ["enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"];

interface Props {
  calendarId: string;
  versionId: string;
  date: string;
  areaId: string;
  areaName: string;
  currentDoctorId?: string;
  currentAssignmentId?: string;
  onConfirm: (doctorId: string, forceWarnings: string[], justification: string) => void;
  onClose: () => void;
  isLoading: boolean;
  onRemove?: () => void;
  submitError?: string | null;
}

type Step = "select" | "evaluating" | "review-warnings";

export function AssignDoctorModal({
  calendarId, date, areaId, areaName,
  currentDoctorId, currentAssignmentId, onConfirm, onClose, isLoading, onRemove, submitError,
}: Props) {
  const [query, setQuery] = useState("");
  // Por defecto solo se ofrecen médicos cuyo día marcado es este (los fijos
  // solo en sus días). El encargado puede activar el interruptor para buscar
  // médicos de otros días; al elegirlos salen las advertencias confirmables.
  const [includeOthers, setIncludeOthers] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(currentDoctorId ?? null);
  const [step, setStep] = useState<Step>("select");
  const [eligibleDoctors, setEligibleDoctors] = useState<EligibleDoctorRead[]>([]);
  const [unavailableDoctors, setUnavailableDoctors] = useState<UnavailableDoctorRead[]>([]);
  const [loadingEligible, setLoadingEligible] = useState(true);
  const [eligibleError, setEligibleError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<WarningItem[]>([]);
  const [acceptedWarnings, setAcceptedWarnings] = useState<Set<string>>(new Set());
  const [justification, setJustification] = useState("");
  const [evaluateError, setEvaluateError] = useState<string | null>(null);

  const [year, month, day] = date.split("-").map(Number);
  const title = `${day} de ${MONTHS[month - 1]} ${year} · ${areaName}`;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadingEligible(true);
      setEligibleError(null);
      try {
        const res = await calendarsApi.eligibleDoctors(calendarId, date, areaId, !includeOthers);
        if (!cancelled) {
          setEligibleDoctors(res.doctors);
          setUnavailableDoctors(res.unavailable ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setEligibleError(
            err instanceof ApiError ? err.message : "Error al cargar doctores disponibles."
          );
        }
      } finally {
        if (!cancelled) setLoadingEligible(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [calendarId, date, areaId, includeOthers]);

  const softUnavailable = unavailableDoctors.filter(u => !u.is_hard && u.doctor_id !== currentDoctorId);
  const hardUnavailable = unavailableDoctors.filter(u => u.is_hard && u.doctor_id !== currentDoctorId);

  type CandidateKind = "available" | "soft" | "hard";
  interface CandidateRow {
    key: string;
    kind: CandidateKind;
    doctorId: string;
    fullName: string;
    reasons?: string[];
    outsidePattern?: boolean;
    alteraOrden?: boolean | null;
  }

  const q = query.trim().toLowerCase();
  const matches = (name: string) => !q || name.toLowerCase().includes(q);

  // Lista única y buscable: disponibles del día primero, luego los demás con
  // motivo (agrupados por médico), y al final los bloqueados (sin clic).
  // El buscador filtra TODA la lista, no solo los del día.
  const softByDoctor = new Map<string, CandidateRow>();
  for (const u of softUnavailable) {
    const existing = softByDoctor.get(u.doctor_id);
    if (existing) {
      if (u.description) existing.reasons!.push(u.description);
      if (u.outside_pattern) existing.outsidePattern = true;
    } else {
      softByDoctor.set(u.doctor_id, {
        key: `soft-${u.doctor_id}`,
        kind: "soft",
        doctorId: u.doctor_id,
        fullName: u.full_name,
        reasons: u.description ? [u.description] : [],
        outsidePattern: !!u.outside_pattern,
      });
    }
  }

  const candidates: CandidateRow[] = [
    ...eligibleDoctors
      .filter(d => d.id !== currentDoctorId && matches(d.full_name))
      .sort((a, b) => {
        // Docs that respect pattern first, then alters, then no pattern
        const pa = a.altera_orden === false ? 0 : a.altera_orden === true ? 1 : 2;
        const pb = b.altera_orden === false ? 0 : b.altera_orden === true ? 1 : 2;
        if (pa !== pb) return pa - pb;
        return a.full_name.localeCompare(b.full_name);
      })
      .map(d => ({
        key: d.id,
        kind: "available" as CandidateKind,
        doctorId: d.id,
        fullName: d.full_name,
        alteraOrden: d.altera_orden,
      })),
    ...[...softByDoctor.values()]
      .filter(r => matches(r.fullName))
      .sort((a, b) => a.fullName.localeCompare(b.fullName)),
    ...hardUnavailable
      .filter(u => matches(u.full_name))
      .sort((a, b) => a.full_name.localeCompare(b.full_name))
      .map(u => ({
        key: `hard-${u.doctor_id}-${u.code}`,
        kind: "hard" as CandidateKind,
        doctorId: u.doctor_id,
        fullName: u.full_name,
        reasons: [u.description],
      })),
  ];

  const handleSelectDoctor = async (doctorId: string) => {
    setSelectedId(doctorId);
    setStep("evaluating");
    setEvaluateError(null);
    try {
      const result = await calendarsApi.evaluate(calendarId, {
        doctor_id: doctorId,
        service_date: date,
        service_area_id: areaId,
        // Reemplazo de un turno ocupado: el ocupante no debe bloquear la evaluación
        replacing_assignment_id: currentAssignmentId ?? null,
      });
      if (result.hard_blocks.length > 0) {
        setEvaluateError(result.hard_blocks.map(b => b.description).join(" "));
        setStep("select");
        return;
      }
      if (result.warnings.length > 0) {
        setWarnings(result.warnings);
        setAcceptedWarnings(new Set());
        setJustification("");
        setStep("review-warnings");
      } else {
        onConfirm(doctorId, [], "");
      }
    } catch (err) {
      setEvaluateError(
        err instanceof ApiError ? err.message : "Error al evaluar la asignación."
      );
      setStep("select");
    }
  };

  const toggleWarning = (code: string) => {
    setAcceptedWarnings(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const allWarningsAccepted = warnings.every(w => acceptedWarnings.has(w.code));

  const handleConfirmWithWarnings = () => {
    onConfirm(selectedId!, Array.from(acceptedWarnings), justification.trim());
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" style={{ maxWidth: 480 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Asignar — {title}</h2>
          <button className="btn-icon" onClick={onClose} aria-label="Cerrar">&times;</button>
        </div>

        {step === "select" && (
          <>
            <div style={{ marginBottom: 10 }}>
              <button
                type="button"
                role="switch"
                aria-checked={includeOthers}
                onClick={() => { setIncludeOthers(v => !v); setQuery(""); }}
                title="Al activarlo se listan también médicos cuyo día marcado no es este; al elegirlos deberás confirmar las advertencias."
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  background: "transparent", border: 0, cursor: "pointer", padding: 0,
                  fontSize: 12.5, color: "#475569", userSelect: "none",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 34, height: 20, borderRadius: 999, flexShrink: 0,
                    background: includeOthers ? "#2563eb" : "#cbd5e1",
                    position: "relative", transition: "background 0.15s ease",
                  }}
                >
                  <span
                    style={{
                      position: "absolute", top: 2, left: includeOthers ? 16 : 2,
                      width: 16, height: 16, borderRadius: "50%", background: "#fff",
                      transition: "left 0.15s ease",
                    }}
                  />
                </span>
                Buscar m&eacute;dicos que no son de este d&iacute;a
              </button>
            </div>

            <div style={{ position: "relative", marginBottom: 12 }}>
              <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#94a3b8" }} />
              <input
                placeholder="Buscar médico…"
                value={query}
                onChange={e => setQuery(e.target.value)}
                style={{ paddingLeft: 32 }}
                autoFocus
              />
            </div>

            {loadingEligible && <p style={{ padding: "12px 16px", color: "#94a3b8" }}>Cargando doctores disponibles…</p>}
            {eligibleError && <p style={{ padding: "12px 16px", color: "#b91c1c" }}>{eligibleError}</p>}

            {!loadingEligible && !eligibleError && (
              <>
                <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
                  {candidates.length === 0 && (
                    <p style={{ padding: "12px 16px", color: "#94a3b8", fontSize: "0.88rem" }}>
                      {q ? "Sin resultados para esa búsqueda." : "No hay médicos para asignar en este turno."}
                    </p>
                  )}
                  {candidates.map(c => {
                    const selected = selectedId === c.doctorId;
                    if (c.kind === "hard") {
                      return (
                        <div
                          key={c.key}
                          style={{
                            display: "flex", alignItems: "center", gap: 8,
                            padding: "7px 16px", borderBottom: "1px solid #f1f5f9",
                            fontSize: 13, background: "#f8fafc", opacity: 0.8,
                          }}
                        >
                          <Lock size={12} style={{ color: "#b91c1c", flexShrink: 0 }} />
                          <span style={{ color: "#991b1b" }}>
                            {c.fullName} — {(c.reasons ?? []).join(" ")}
                          </span>
                        </div>
                      );
                    }
                    return (
                      <button
                        key={c.key}
                        onClick={() => handleSelectDoctor(c.doctorId)}
                        style={{
                          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                          gap: 8, padding: "8px 16px",
                          background: selected ? "#bfdbfe" : "transparent",
                          border: 0, borderBottom: "1px solid #f1f5f9", cursor: "pointer",
                          textAlign: "left", fontSize: "0.9rem",
                        }}
                      >
                        <span style={{ minWidth: 0, flex: 1 }}>
                          <span style={{ display: "block", fontWeight: selected ? 700 : 500, color: "#1e293b" }}>
                            {c.fullName}
                          </span>
                          {c.kind === "soft" && (
                            <>
                              {c.outsidePattern && (
                                <span style={{ display: "block", fontSize: 11.5, color: "#b45309" }}>
                                  No es de este d&iacute;a (d&iacute;a marcado distinto)
                                </span>
                              )}
                              <span style={{ display: "block", fontSize: 12, color: "#b45309" }}>
                                {(c.reasons ?? []).join(" · ")}
                              </span>
                            </>
                          )}
                        </span>
                        {c.kind === "available" && c.alteraOrden === false && (
                          <span className="order-indicator order-respeta">
                            <CheckCircle2 size={14} /> Respeta el orden
                          </span>
                        )}
                        {c.kind === "available" && c.alteraOrden === true && (
                          <span className="order-indicator order-altera">
                            <AlertTriangle size={14} /> Altera el orden
                          </span>
                        )}
                        {c.kind === "available" && c.alteraOrden === null && (
                          <span className="order-indicator order-sin-patron">Sin orden fijo</span>
                        )}
                        {c.kind === "soft" && (
                          <span
                            className="btn-ghost"
                            style={{ fontSize: 11, padding: "2px 6px", whiteSpace: "nowrap", pointerEvents: "none" }}
                          >
                            Elegir
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {evaluateError && (
              <div style={{ marginTop: 12, padding: "10px 12px", border: "1px solid #fecaca", borderRadius: 6, background: "#fef2f2" }}>
                <strong style={{ display: "block", fontSize: 13, color: "#991b1b", marginBottom: 4 }}>No se puede asignar</strong>
                <p style={{ margin: 0, fontSize: 13, color: "#991b1b" }}>{evaluateError}</p>
              </div>
            )}

            <div className="form-footer" style={{ marginTop: 16 }}>
              <button className="btn-secondary" onClick={onClose}>Cancelar</button>
              {onRemove && (
                <button className="btn-secondary" onClick={onRemove} style={{ marginRight: "auto", color: "#b91c1c", borderColor: "#fecaca" }}>
                  Quitar asignación
                </button>
              )}
              <div />
            </div>
          </>
        )}

        {step === "evaluating" && (
          <div style={{ padding: "24px 16px", textAlign: "center" }}>
            <p style={{ color: "#64748b" }}>Evaluando reglas…</p>
          </div>
        )}

        {step === "review-warnings" && (
          <>
            <div style={{ marginTop: 12, padding: "10px 12px", border: "1px solid #fed7aa", borderRadius: 6, background: "#fff7ed" }}>
              <strong style={{ display: "block", fontSize: 13, color: "#9a3412", marginBottom: 8 }}>
                Advertencias de reglas
              </strong>
              <p style={{ margin: "0 0 12px", fontSize: 13, color: "#9a3412" }}>
                Esta asignación genera las siguientes advertencias. Marca cada una para confirmar que deseas continuar.
              </p>
              {warnings.map(w => (
                <label
                  key={w.code}
                  style={{
                    display: "flex", alignItems: "flex-start", gap: 8,
                    padding: "8px 0", borderBottom: "1px solid #fed7aa",
                    cursor: "pointer", fontSize: 13,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={acceptedWarnings.has(w.code)}
                    onChange={() => toggleWarning(w.code)}
                    style={{ marginTop: 2 }}
                  />
                  <span style={{ color: "#9a3412" }}>{w.description}</span>
                </label>
              ))}
            </div>

            <div style={{ marginTop: 12 }}>
              <label style={{ display: "block", fontSize: 13, color: "#475569", marginBottom: 4 }}>
                Justificación (opcional)
              </label>
              <textarea
                value={justification}
                onChange={e => setJustification(e.target.value)}
                placeholder="Ej. Necesidad operativa: es el único disponible para cubrir el servicio."
                rows={3}
                maxLength={500}
                style={{ width: "100%", fontSize: 13 }}
              />
            </div>

            {submitError && (
              <div style={{ marginTop: 12, padding: "10px 12px", border: "1px solid #fecaca", borderRadius: 6, background: "#fef2f2" }}>
                <strong style={{ display: "block", fontSize: 13, color: "#991b1b", marginBottom: 4 }}>No se pudo asignar</strong>
                <p style={{ margin: 0, fontSize: 13, color: "#991b1b" }}>{submitError}</p>
              </div>
            )}

            <div className="form-footer" style={{ marginTop: 16 }}>
              <button className="btn-secondary" onClick={() => { setStep("select"); setWarnings([]); setJustification(""); }}>
                Volver
              </button>
              <button
                className="btn-primary"
                onClick={handleConfirmWithWarnings}
                disabled={!allWarningsAccepted || isLoading}
              >
                {isLoading ? "Asignando…" : "Asignar con advertencias"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
