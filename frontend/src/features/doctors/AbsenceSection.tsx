import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarOff, Check, Pencil, PlusCircle, Trash2 } from "lucide-react";
import {
  availabilityApi,
  DeactivationReasonRead,
  DoctorRestrictionRead,
} from "../../api/doctors";
import { useToast } from "../../components/Toast";

/**
 * "No disponible" (eje 2: fuera de servicio).
 *
 * El sistema guarda esta ausencia de **dos maneras** y el encargado no tiene por qué
 * saberlo: el flag `service_active` (sin fechas, "hasta que alguien lo reactive") y una
 * restricción con fechas, que es la que deja al médico fuera **solo** en el rango y lo
 * devuelve solo. Esta sección muestra las dos juntas, con la fecha de reintegro destacada
 * porque es el dato que se busca.
 *
 * Una ausencia con fecha de regreso avisa al encargado unos días antes; una **indefinida**
 * (o el flag sin fechas) no avisa, porque no hay fecha de la que avisar.
 */

interface Props {
  doctorId: string;
  reasons: DeactivationReasonRead[];
  /** El flag sin fechas: si el médico está fuera de servicio "hasta nuevo aviso". */
  serviceActive: boolean;
  inactiveReasonName: string | null;
  inactiveDetail: string | null;
}

const SEVERITY = "hard_block";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

/** Estado de una ausencia respecto a hoy. */
function stateOf(restriction: DoctorRestrictionRead): "vigente" | "programada" | "finalizada" {
  const today = todayISO();
  if (restriction.starts_at > today) return "programada";
  if (restriction.ends_at !== null && restriction.ends_at < today) return "finalizada";
  return "vigente";
}

export function AbsenceSection({
  doctorId,
  reasons,
  serviceActive,
  inactiveReasonName,
  inactiveDetail,
}: Props) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [reasonId, setReasonId] = useState("");
  const [startsAt, setStartsAt] = useState(todayISO());
  const [endsAt, setEndsAt] = useState("");
  const [indefinite, setIndefinite] = useState(false);
  const [formError, setFormError] = useState("");

  const { data: restrictions } = useQuery({
    queryKey: ["restrictions", doctorId],
    queryFn: () => availabilityApi.listRestrictions(doctorId),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["restrictions", doctorId] });
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        severity: SEVERITY,
        starts_at: startsAt,
        ends_at: indefinite ? null : endsAt,
        reason_id: reasonId || null,
      };
      return editingId
        ? availabilityApi.updateRestriction(editingId, payload)
        : availabilityApi.addRestriction(doctorId, {
            ...payload,
            restriction_type: "license",
          });
    },
    onSuccess: () => {
      addToast("success", editingId ? "Ausencia actualizada." : "Ausencia registrada.");
      closeForm();
      invalidate();
    },
    onError: (error: Error) => setFormError(error.message || "No se pudo guardar la ausencia."),
  });

  const liftMutation = useMutation({
    mutationFn: (id: string) => availabilityApi.liftRestriction(id),
    onSuccess: () => {
      addToast("success", "Ausencia levantada. El médico vuelve a estar disponible.");
      invalidate();
    },
    onError: () => addToast("error", "No se pudo levantar la ausencia."),
  });

  function resetForm() {
    setEditingId(null);
    setReasonId("");
    setStartsAt(todayISO());
    setEndsAt("");
    setIndefinite(false);
    setFormError("");
  }

  function closeForm() {
    setShowForm(false);
    resetForm();
  }

  function startEditing(restriction: DoctorRestrictionRead) {
    setEditingId(restriction.id);
    setReasonId(restriction.reason_id ?? "");
    setStartsAt(restriction.starts_at);
    setEndsAt(restriction.ends_at ?? "");
    setIndefinite(restriction.ends_at === null);
    setFormError("");
    setShowForm(true);
  }

  /** El motivo **propone**, no impone: si no espera regreso, se marca Indefinido solo. */
  function handleReasonChange(value: string) {
    setReasonId(value);
    const reason = reasons.find(r => r.id === value);
    if (reason && !reason.expects_return) {
      setIndefinite(true);
      setEndsAt("");
    }
  }

  function handleSubmit() {
    if (!startsAt) {
      setFormError("Indica desde cuándo no está disponible.");
      return;
    }
    if (!indefinite && !endsAt) {
      setFormError("Indica la fecha de regreso o marca Indefinido.");
      return;
    }
    if (!indefinite && endsAt < startsAt) {
      setFormError("La fecha de regreso no puede ser anterior a la de inicio.");
      return;
    }
    setFormError("");
    saveMutation.mutate();
  }

  const active = (restrictions ?? []).filter(r => r.lifted_at === null);
  const visible = active.filter(r => stateOf(r) !== "finalizada");
  const past = active.filter(r => stateOf(r) === "finalizada");

  return (
    <section className="profile-section">
      <h3>
        <CalendarOff size={15} /> No disponible
      </h3>

      {visible.length === 0 && serviceActive && (
        <p className="profile-empty">Sin ausencias registradas.</p>
      )}

      {/* La ausencia sin fechas: el flag del sistema, no una ausencia con regreso. */}
      {!serviceActive && (
        <div className="absence-row absence-row--flag">
          <div>
            <strong>{inactiveReasonName ?? "Fuera de servicio"}</strong>
            <span className="absence-dates">Sin fecha de regreso (hasta reactivarlo)</span>
            {inactiveDetail && <span className="absence-detail">{inactiveDetail}</span>}
          </div>
          <span className="absence-badge absence-badge--vigente">Vigente</span>
        </div>
      )}

      {visible.map(restriction => {
        const reason = reasons.find(r => r.id === restriction.reason_id);
        const state = stateOf(restriction);
        return (
          <div className="absence-row" key={restriction.id}>
            <div>
              <strong>{reason?.display_name ?? "Sin motivo"}</strong>
              <span className="absence-dates">
                {formatDate(restriction.starts_at)} →{" "}
                {restriction.ends_at === null ? (
                  <em>Indefinido (no avisa)</em>
                ) : (
                  <em>se reintegra el {formatDate(restriction.ends_at)}</em>
                )}
              </span>
            </div>
            <span className={`absence-badge absence-badge--${state}`}>
              {state === "vigente" ? "Vigente" : "Programada"}
            </span>
            <div className="absence-actions">
              <button
                className="btn-ghost"
                style={{ padding: "3px 8px" }}
                title="Editar ausencia"
                onClick={() => startEditing(restriction)}
              >
                <Pencil size={13} />
              </button>
              <button
                className="btn-ghost btn-danger"
                style={{ padding: "3px 8px" }}
                title="Levantar ausencia (el médico vuelve hoy)"
                onClick={() => liftMutation.mutate(restriction.id)}
                disabled={liftMutation.isPending}
              >
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        );
      })}

      {past.length > 0 && (
        <details style={{ marginTop: "8px" }}>
          <summary style={{ cursor: "pointer", fontSize: "0.82rem", color: "#64748b" }}>
            Ausencias anteriores ({past.length})
          </summary>
          {past.map(restriction => (
            <div className="absence-row absence-row--past" key={restriction.id}>
              <div>
                <strong>
                  {reasons.find(r => r.id === restriction.reason_id)?.display_name ??
                    "Sin motivo"}
                </strong>
                <span className="absence-dates">
                  {formatDate(restriction.starts_at)} →{" "}
                  {restriction.ends_at ? formatDate(restriction.ends_at) : "Indefinido"}
                </span>
              </div>
            </div>
          ))}
        </details>
      )}

      {!showForm && (
        <button
          className="btn-secondary"
          style={{ marginTop: "10px" }}
          onClick={() => {
            resetForm();
            setShowForm(true);
          }}
        >
          <PlusCircle size={15} /> Registrar ausencia
        </button>
      )}

      {showForm && (
        <div className="absence-form">
          <h4>{editingId ? "Editar ausencia" : "Registrar ausencia"}</h4>
          <label>
            Motivo
            <select value={reasonId} onChange={e => handleReasonChange(e.target.value)}>
              <option value="">Seleccionar motivo</option>
              {reasons.filter(r => r.active).map(r => (
                <option key={r.id} value={r.id}>
                  {r.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Desde
            <input type="date" value={startsAt} onChange={e => setStartsAt(e.target.value)} />
          </label>
          <label className="toggle-label" style={{ margin: 0 }}>
            <input
              type="checkbox"
              checked={indefinite}
              onChange={e => {
                setIndefinite(e.target.checked);
                if (e.target.checked) setEndsAt("");
              }}
            />
            Indefinido
          </label>
          <label>
            Hasta (fecha de regreso)
            <input
              type="date"
              value={endsAt}
              disabled={indefinite}
              onChange={e => setEndsAt(e.target.value)}
            />
          </label>
          <p className="absence-hint">
            {indefinite
              ? "Indefinido: el médico queda fuera desde esa fecha y no se avisa a nadie, porque no hay fecha de regreso."
              : "Se avisará al encargado unos días antes de la fecha de regreso."}
          </p>
          {formError && <p className="form-error">{formError}</p>}
          <div className="profile-actions">
            <button className="btn-primary" onClick={handleSubmit} disabled={saveMutation.isPending}>
              <Check size={15} /> {saveMutation.isPending ? "Guardando…" : "Guardar"}
            </button>
            <button className="btn-secondary" onClick={closeForm}>
              Cancelar
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
