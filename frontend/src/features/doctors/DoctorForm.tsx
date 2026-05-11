import { Save, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { doctorsApi, availabilityApi, CreateDoctorPayload, DoctorRead } from "../../api/doctors";

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
  const [target, setTarget] = useState(String(doctor?.monthly_service_target ?? 3));
  const [max, setMax] = useState(String(doctor?.monthly_service_max ?? 3));
  const [limitMode, setLimitMode] = useState(doctor?.monthly_service_limit_mode ?? "warn_only");
  const [rankId, setRankId] = useState<string>(doctor?.rank_id ?? "");
  const [allowedAreaIds, setAllowedAreaIds] = useState<string[]>(doctor?.allowed_area_ids ?? []);

  const DAY_LABELS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
  const DAY_TO_BACKEND = [6, 0, 1, 2, 3, 4, 5];
  const WEEK_LABELS = ["1ra", "2da", "3ra", "4ta", "Última"];
  const WEEK_VALUES = [0, 1, 2, 3, -1];

  const [avMode, setAvMode] = useState<"weekly" | "monthly" | "recurring">("weekly");
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [selectedDates, setSelectedDates] = useState<number[]>([]);
  const [selectedWeekday, setSelectedWeekday] = useState<number>(4);
  const [selectedWeekNumber, setSelectedWeekNumber] = useState<number>(-1);

  function toggleDay(backendDay: number) {
    setSelectedDays(prev =>
      prev.includes(backendDay) ? prev.filter(d => d !== backendDay) : [...prev, backendDay]
    );
  }

  function toggleDate(day: number) {
    setSelectedDates(prev =>
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
    );
  }
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
    onSuccess: async (savedDoctor) => {
      const doctorId = savedDoctor.id;
      try {
        if (avMode === "weekly" && selectedDays.length > 0) {
          await availabilityApi.setWeekly(doctorId, { days_of_week: selectedDays });
        } else if (avMode === "monthly" && selectedDates.length > 0) {
          const now = new Date();
          await availabilityApi.setMonthly(doctorId, {
            year: now.getFullYear(),
            month: now.getMonth() + 1,
            available_dates: selectedDates,
          });
        } else if (avMode === "recurring") {
          await availabilityApi.setRecurring(doctorId, {
            weekday: selectedWeekday,
            week_number: selectedWeekNumber,
          });
        }
      } catch {
        setError("Médico guardado, pero no se pudo configurar la disponibilidad.");
        return;
      }
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

    if (avMode === "weekly" && selectedDays.length === 0) { setError("Selecciona al menos un día de la semana."); return; }
    if (avMode === "monthly" && selectedDates.length === 0) { setError("Selecciona al menos un día del mes."); return; }

    const availabilityMode = avMode === "monthly" ? "monthly" : "fixed";

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
            <fieldset className="field-group">
              <legend>Disponibilidad</legend>
              <div className="av-toggle-group">
                <button type="button"
                  className={`av-toggle-btn${avMode === "weekly" ? " av-toggle-btn--active" : ""}`}
                  onClick={() => setAvMode("weekly")}>
                  Mismos días<br />todas las semanas
                </button>
                <button type="button"
                  className={`av-toggle-btn${avMode === "monthly" ? " av-toggle-btn--active" : ""}`}
                  onClick={() => setAvMode("monthly")}>
                  Avisa sus días<br />cada mes
                </button>
                <button type="button"
                  className={`av-toggle-btn${avMode === "recurring" ? " av-toggle-btn--active" : ""}`}
                  onClick={() => setAvMode("recurring")}>
                  Día fijo<br />al mes
                </button>
              </div>
              {avMode === "weekly" && (
                <div className="av-day-checks">
                  {DAY_LABELS.map((label, i) => {
                    const backendDay = DAY_TO_BACKEND[i];
                    const selected = selectedDays.includes(backendDay);
                    return (
                      <label key={label} className="check-label">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleDay(backendDay)}
                        />
                        {label}
                      </label>
                    );
                  })}
                </div>
              )}
              {avMode === "monthly" && (
                <div className="av-month-grid">
                  {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                    <button key={day} type="button"
                      className={`av-month-day${selectedDates.includes(day) ? " av-month-day--selected" : ""}`}
                      onClick={() => toggleDate(day)}>
                      {day}
                    </button>
                  ))}
                </div>
              )}
              {avMode === "recurring" && (
                <div className="av-recurring-row">
                  <div className="av-recurring-col">
                    <span className="av-recurring-label">Día</span>
                    {DAY_LABELS.map((label, i) => {
                      const backendDay = DAY_TO_BACKEND[i];
                      return (
                        <button key={label} type="button"
                          className={`av-recurring-chip${selectedWeekday === backendDay ? " av-recurring-chip--selected" : ""}`}
                          onClick={() => setSelectedWeekday(backendDay)}>
                          {label}
                        </button>
                      );
                    })}
                  </div>
                  <div className="av-recurring-col">
                    <span className="av-recurring-label">Semana</span>
                    {WEEK_LABELS.map((label, i) => (
                      <button key={label} type="button"
                        className={`av-recurring-chip${selectedWeekNumber === WEEK_VALUES[i] ? " av-recurring-chip--selected" : ""}`}
                        onClick={() => setSelectedWeekNumber(WEEK_VALUES[i])}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </fieldset>
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
