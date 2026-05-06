import { Save, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { doctorsApi, CreateDoctorPayload, DoctorRead } from "../../api/doctors";

interface Props {
  doctor?: DoctorRead;
  onClose: () => void;
}

export function DoctorForm({ doctor, onClose }: Props) {
  const qc = useQueryClient();
  const isEdit = !!doctor;

  const [name, setName] = useState(doctor?.name ?? "");
  const [sex, setSex] = useState(doctor?.sex ?? "male");
  const [phone, setPhone] = useState(doctor?.phone ?? "");
  const [participaMisiones, setParticipaMisiones] = useState(doctor?.participa_misiones ?? true);
  const [availabilityMode, setAvailabilityMode] = useState(doctor?.availability_mode ?? "monthly");
  const [target, setTarget] = useState(String(doctor?.monthly_service_target ?? 3));
  const [max, setMax] = useState(String(doctor?.monthly_service_max ?? 3));
  const [limitMode, setLimitMode] = useState(doctor?.monthly_service_limit_mode ?? "warn_only");
  const [rankId, setRankId] = useState<string>(doctor?.rank_id ?? "");
  const [allowedAreaIds, setAllowedAreaIds] = useState<string[]>(doctor?.allowed_area_ids ?? []);
  const [error, setError] = useState("");

  const { data: serviceAreas } = useQuery({
    queryKey: ["service-areas"],
    queryFn: doctorsApi.listServiceAreas,
  });

  const { data: ranks } = useQuery({
    queryKey: ["ranks"],
    queryFn: doctorsApi.listRanks,
  });

  const save = useMutation({
    mutationFn: (payload: CreateDoctorPayload) =>
      isEdit ? doctorsApi.update(doctor!.id, payload) : doctorsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doctors"] });
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const t = parseInt(target, 10);
    const m = parseInt(max, 10);
    if (isNaN(t) || isNaN(m)) { setError("Meta y máximo deben ser números."); return; }
    save.mutate({
      name, sex, phone: phone || null, participa_misiones: participaMisiones,
      rank_id: rankId || null,
      availability_mode: availabilityMode,
      monthly_service_target: t, monthly_service_max: m,
      monthly_service_limit_mode: limitMode,
      allowed_area_ids: allowedAreaIds,
    });
  }

  function toggleArea(id: string) {
    setAllowedAreaIds(prev =>
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal-panel">
        <div className="modal-header">
          <h2>{isEdit ? "Editar médico" : "Nuevo médico"}</h2>
          <button className="btn-icon" onClick={onClose}><X size={20} /></button>
        </div>

        <form className="doctor-form" onSubmit={handleSubmit}>
          <div className="form-row">
            <label>
              Nombre completo
              <input required value={name} onChange={e => setName(e.target.value)} />
            </label>
            <label>
              Sexo
              <select value={sex} onChange={e => setSex(e.target.value)}>
                <option value="male">Masculino</option>
                <option value="female">Femenino</option>
              </select>
            </label>
          </div>

          <div className="form-row">
            <label>
              Rango
              <select value={rankId} onChange={e => setRankId(e.target.value)}>
                <option value="">— Sin rango —</option>
                {(ranks ?? []).map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </label>
            <label>
              Teléfono
              <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="Opcional" />
            </label>
          </div>

          <div className="form-row">
            <label>
              Meta mensual
              <input type="number" min={0} value={target} onChange={e => setTarget(e.target.value)} />
            </label>
            <label>
              Máximo mensual
              <input type="number" min={0} value={max} onChange={e => setMax(e.target.value)} />
            </label>
            <label>
              Modo límite
              <select value={limitMode} onChange={e => setLimitMode(e.target.value)}>
                <option value="warn_only">Solo advertencia</option>
                <option value="hard_limit">Límite estricto</option>
              </select>
            </label>
          </div>

          <div className="form-row">
            <label>
              Modo disponibilidad
              <select value={availabilityMode} onChange={e => setAvailabilityMode(e.target.value)}>
                <option value="monthly">Variable mensual</option>
                <option value="fixed">Fijo semanal</option>
              </select>
            </label>
          </div>

          <fieldset className="field-group">
            <legend>Áreas de servicio permitidas</legend>
            <div className="area-checks">
              {(serviceAreas ?? []).filter(a => a.active).map(area => (
                <label key={area.id} className="check-label">
                  <input
                    type="checkbox"
                    checked={allowedAreaIds.includes(area.id)}
                    onChange={() => toggleArea(area.id)}
                  />
                  {area.display_name}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="check-label">
            <input
              type="checkbox"
              checked={participaMisiones}
              onChange={e => setParticipaMisiones(e.target.checked)}
            />
            Participa en misiones
          </label>

          {error && <p className="form-error">{error}</p>}

          <div className="form-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>
              <Save size={16} />
              {save.isPending ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
