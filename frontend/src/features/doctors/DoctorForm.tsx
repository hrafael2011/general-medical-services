import { FormEvent, useEffect, useState } from "react";
import { Save, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DayPicker } from "react-day-picker";
import "react-day-picker/style.css";
import { doctorsApi, availabilityApi, CreateDoctorPayload, DoctorRead } from "../../api/doctors";

interface Props {
  doctor?: DoctorRead;
  onClose: () => void;
}

export function DoctorForm({ doctor, onClose }: Props) {
  const qc = useQueryClient();
  const isEdit = !!doctor;

  const initialNameParts = splitDoctorName(doctor);
  const [firstName, setFirstName] = useState(initialNameParts.firstName);
  const [lastName, setLastName] = useState(initialNameParts.lastName);
  const [sex, setSex] = useState(doctor?.sex ?? "male");
  const [phone, setPhone] = useState(doctor?.whatsapp_phone ?? "");
  const [participaMisiones, setParticipaMisiones] = useState(doctor?.participa_misiones ?? true);
  const [doesService, setDoesService] = useState(doctor?.service_active ?? true);
  const [target, setTarget] = useState(String(doctor?.monthly_service_target ?? 3));
  const [max, setMax] = useState(String(doctor?.monthly_service_max ?? 3));
  const [limitMode, setLimitMode] = useState(doctor?.monthly_service_limit_mode ?? "warn_only");
  const [rankId, setRankId] = useState<string>(doctor?.rank_id ?? "");
  const [departmentId, setDepartmentId] = useState<string>(doctor?.department_id ?? "");
  const [allowedAreaIds, setAllowedAreaIds] = useState<string[]>(doctor?.allowed_area_ids ?? []);

  const MAX_WEEKLY_DAYS = 2;
  const DAY_LABELS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
  const DAY_TO_BACKEND = [6, 0, 1, 2, 3, 4, 5];
  const WEEK_LABELS = ["1ra", "2da", "3ra", "4ta", "Última"];
  const WEEK_VALUES = [0, 1, 2, 3, -1];

  const [avMode, setAvMode] = useState<"weekly" | "monthly" | "recurring">(
    doctor?.availability_mode === "monthly" ? "monthly" : "weekly"
  );
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [selectedDates, setSelectedDates] = useState<Date[]>([]);
  const [selectedWeekday, setSelectedWeekday] = useState<number>(4);
  const [selectedWeekNumber, setSelectedWeekNumber] = useState<number>(-1);

  function toggleDay(backendDay: number) {
    setSelectedDays(prev => {
      if (prev.includes(backendDay)) return prev.filter(d => d !== backendDay);
      if (prev.length >= MAX_WEEKLY_DAYS) return prev;
      return [...prev, backendDay];
    });
  }

  function handleDayPickerSelect(dates: Date[] | undefined) {
    setSelectedDates(dates ?? []);
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

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: doctorsApi.listDepartments,
  });

  const { data: availabilityData } = useQuery({
    queryKey: ["doctor-availability", doctor?.id],
    queryFn: () => availabilityApi.list(doctor!.id),
    enabled: isEdit,
  });

  useEffect(() => {
    if (!availabilityData || availabilityData.length === 0) return;

    const weekly = availabilityData.find(a => a.availability_type === "weekly_fixed");
    const recurring = availabilityData.find(a => a.availability_type === "recurring");
    const monthly = availabilityData.find(a => a.availability_type === "monthly_variable");

    if (weekly && doctor?.availability_mode !== "monthly") {
      setAvMode("weekly");
      setSelectedDays(weekly.days_of_week ?? []);
    } else if (recurring) {
      setAvMode("recurring");
      setSelectedWeekday(recurring.weekday ?? 4);
      setSelectedWeekNumber(recurring.week_number ?? -1);
    } else if (monthly) {
      setAvMode("monthly");
      const year = monthly.year ?? new Date().getFullYear();
      const month = monthly.month ?? new Date().getMonth() + 1;
      setSelectedDates(
        (monthly.available_dates ?? []).map(d => new Date(year, month - 1, d))
      );
    }
  }, [availabilityData, doctor?.availability_mode]);

  const save = useMutation({
    mutationFn: (payload: CreateDoctorPayload) =>
      isEdit ? doctorsApi.update(doctor!.id, payload) : doctorsApi.create(payload),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const t = parseInt(target, 10);
    const m = parseInt(max, 10);
    if (isNaN(t) || isNaN(m)) { setError("Meta y máximo deben ser números."); return; }

    if (doesService) {
      if (avMode === "weekly" && selectedDays.length === 0) { setError("Selecciona al menos un día de la semana."); return; }
      if (allowedAreaIds.length === 0) { setError("Selecciona al menos un área de servicio."); return; }
    }

    const availabilityMode = avMode === "monthly" ? "monthly" : "fixed";

    const cleanFirstName = firstName.trim();
    const cleanLastName = lastName.trim();
    const fullName = [cleanFirstName, cleanLastName].filter(Boolean).join(" ");
    if (!cleanFirstName || !cleanLastName) { setError("Nombre y apellido son obligatorios."); return; }
    if (!phone.trim()) { setError("WhatsApp es obligatorio."); return; }

    save.mutate({
      first_name: cleanFirstName,
      last_name: cleanLastName,
      name: fullName,
      sex, whatsapp_phone: phone.trim(), participa_misiones: participaMisiones,
      rank_id: rankId || null,
      department_id: departmentId || null,
      availability_mode: availabilityMode,
      monthly_service_target: t, monthly_service_max: m,
      monthly_service_limit_mode: limitMode,
      service_active: doesService,
      allowed_area_ids: doesService ? allowedAreaIds : [],
    }, {
      onSuccess: async (savedDoctor) => {
        const doctorId = savedDoctor.id;
        if (doesService) {
          try {
            if (avMode === "weekly" && selectedDays.length > 0) {
              await availabilityApi.setWeekly(doctorId, { days_of_week: selectedDays });
            } else if (avMode === "monthly" && selectedDates.length > 0) {
              const dates = selectedDates;
              const year = dates[0].getFullYear();
              const month = dates[0].getMonth() + 1;
              const dayNumbers = dates.map(d => d.getDate());
              await availabilityApi.setMonthly(doctorId, {
                year,
                month,
                available_dates: dayNumbers,
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
        }
        qc.invalidateQueries({ queryKey: ["doctors"] });
        onClose();
      },
      onError: (err: Error) => setError(err.message),
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
              Nombre
              <input required value={firstName} onChange={e => setFirstName(e.target.value)} />
            </label>
            <label>
              Apellido
              <input required value={lastName} onChange={e => setLastName(e.target.value)} />
            </label>
          </div>

          <div className="form-row">
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
                {(ranks ?? []).filter(r => r.active).map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </label>
            <label>
              Departamento
              <select value={departmentId} onChange={e => setDepartmentId(e.target.value)}>
                <option value="">— Sin departamento —</option>
                {(departments ?? []).filter(d => d.active).map(d => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="form-row">
            <label>
              WhatsApp *
              <input required value={phone} onChange={e => setPhone(e.target.value)} />
            </label>
          </div>

          <label className="check-label">
            <input
              type="checkbox"
              checked={doesService}
              onChange={e => {
                setDoesService(e.target.checked);
                if (!e.target.checked) {
                  setAllowedAreaIds([]);
                }
              }}
            />
            ¿Hace servicio?
          </label>

          {doesService && (
          <>
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
                    const atLimit = selectedDays.length >= MAX_WEEKLY_DAYS && !selected;
                    return (
                      <label key={label} className={`check-label${atLimit ? " check-label-disabled" : ""}`}>
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={atLimit}
                          onChange={() => toggleDay(backendDay)}
                        />
                        {label}
                      </label>
                    );
                  })}
                </div>
              )}
              {avMode === "monthly" && (
                <div className="av-calendar">
                  <DayPicker
                    mode="multiple"
                    selected={selectedDates}
                    onSelect={handleDayPickerSelect}
                    startMonth={new Date()}
                    defaultMonth={new Date()}
                    showOutsideDays={false}
                  />
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
          </>
          )}

          {!doesService && (
          <p style={{ color: "#64748b", fontSize: "0.85rem", margin: "8px 0" }}>
            El médico no estará disponible para turnos de servicio.
          </p>
          )}

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

function splitDoctorName(doctor?: DoctorRead): { firstName: string; lastName: string } {
  if (!doctor) return { firstName: "", lastName: "" };
  if (doctor.first_name || doctor.last_name) {
    return { firstName: doctor.first_name ?? "", lastName: doctor.last_name ?? "" };
  }
  const parts = doctor.name.trim().split(/\s+/);
  if (parts.length <= 1) return { firstName: doctor.name, lastName: "" };
  return { firstName: parts[0], lastName: parts.slice(1).join(" ") };
}
