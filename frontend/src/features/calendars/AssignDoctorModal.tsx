import { useState, useEffect } from "react";
import { Search } from "lucide-react";
import { EligibleDoctorRead, WarningItem, calendarsApi } from "../../api/calendars";
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
  onConfirm: (doctorId: string, forceWarnings: string[]) => void;
  onClose: () => void;
  isLoading: boolean;
  onRemove?: () => void;
}

type Step = "select" | "evaluating" | "review-warnings";

export function AssignDoctorModal({
  calendarId, versionId, date, areaId, areaName,
  currentDoctorId, onConfirm, onClose, isLoading, onRemove,
}: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(currentDoctorId ?? null);
  const [step, setStep] = useState<Step>("select");
  const [eligibleDoctors, setEligibleDoctors] = useState<EligibleDoctorRead[]>([]);
  const [loadingEligible, setLoadingEligible] = useState(true);
  const [eligibleError, setEligibleError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<WarningItem[]>([]);
  const [acceptedWarnings, setAcceptedWarnings] = useState<Set<string>>(new Set());
  const [evaluateError, setEvaluateError] = useState<string | null>(null);

  const [year, month, day] = date.split("-").map(Number);
  const title = `${day} de ${MONTHS[month - 1]} ${year} · ${areaName}`;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadingEligible(true);
      setEligibleError(null);
      try {
        const res = await calendarsApi.eligibleDoctors(calendarId, date, areaId);
        if (!cancelled) setEligibleDoctors(res.doctors);
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
  }, [calendarId, date, areaId]);

  const filtered = eligibleDoctors.filter(d => {
    if (!d.full_name.toLowerCase().includes(query.toLowerCase())) return false;
    if (d.id === currentDoctorId) return false;
    return true;
  });

  const handleSelectDoctor = async (doctorId: string) => {
    setSelectedId(doctorId);
    setStep("evaluating");
    setEvaluateError(null);
    try {
      const result = await calendarsApi.evaluate(calendarId, {
        doctor_id: doctorId,
        service_date: date,
        service_area_id: areaId,
      });
      if (result.hard_blocks.length > 0) {
        setEvaluateError(result.hard_blocks.map(b => b.description).join(" "));
        setStep("select");
        return;
      }
      if (result.warnings.length > 0) {
        setWarnings(result.warnings);
        setAcceptedWarnings(new Set());
        setStep("review-warnings");
      } else {
        onConfirm(doctorId, []);
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" style={{ maxWidth: 480 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Asignar — {title}</h2>
          <button className="btn-icon" onClick={onClose} aria-label="Cerrar">&times;</button>
        </div>

        {step === "select" && (
          <>
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
              <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
                {filtered.length === 0 && (
                  <p style={{ padding: "12px 16px", color: "#94a3b8", fontSize: "0.88rem" }}>
                    {query ? "Sin resultados." : "No hay doctores disponibles para este slot."}
                  </p>
                )}
                {filtered.map(doc => (
                  <button
                    key={doc.id}
                    onClick={() => handleSelectDoctor(doc.id)}
                    style={{
                      width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "10px 16px",
                      background: selectedId === doc.id ? "#bfdbfe" : "transparent",
                      border: 0, borderBottom: "1px solid #f1f5f9", cursor: "pointer",
                      textAlign: "left", fontSize: "0.9rem",
                    }}
                  >
                    <span style={{ fontWeight: selectedId === doc.id ? 700 : 400, color: "#1e293b" }}>{doc.full_name}</span>
                    <span style={{ fontSize: "0.78rem", color: "#166534" }}>&#10003; activo</span>
                  </button>
                ))}
              </div>
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

            <div className="form-footer" style={{ marginTop: 16 }}>
              <button className="btn-secondary" onClick={() => { setStep("select"); setWarnings([]); }}>
                Volver
              </button>
              <button
                className="btn-primary"
                onClick={() => onConfirm(selectedId!, Array.from(acceptedWarnings))}
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
