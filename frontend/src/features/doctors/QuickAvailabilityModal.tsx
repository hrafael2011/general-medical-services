import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { DayPicker } from "react-day-picker";
import { useQuery } from "@tanstack/react-query";
import { es } from "date-fns/locale";
import "react-day-picker/style.css";
import { availabilityApi } from "../../api/doctors";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";

interface Props {
  doctorId: string;
  doctorName: string;
  initialDates: Date[];
  onClose: () => void;
  onSaved: () => void;
}

export function QuickAvailabilityModal({
  doctorId,
  doctorName,
  initialDates,
  onClose,
  onSaved,
}: Props) {
  const { addToast } = useToast();
  const [selectedDates, setSelectedDates] = useState<Date[]>(initialDates);
  const [saving, setSaving] = useState(false);

  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1; // JS months are 0-indexed

  // Preselecciona los días ya guardados del mes mostrado: al reabrir el modal
  // se ven los días previos (antes abría siempre vacío y parecía que no se guardaban).
  const { data: availability } = useQuery({
    queryKey: ["doctor-availability", doctorId],
    queryFn: () => availabilityApi.list(doctorId),
  });

  useEffect(() => {
    if (!availability?.length) return;
    const saved = availability.find(
      (a) => a.availability_type === "monthly_variable" && a.year === year && a.month === month,
    );
    if (saved?.available_dates?.length) {
      setSelectedDates(saved.available_dates.map((day) => new Date(year, month - 1, day)));
    }
  }, [availability, year, month]);

  const dayNumbers = selectedDates
    .map((d) => d.getDate())
    .sort((a, b) => a - b);

  const handleSave = async () => {
    if (dayNumbers.length === 0) return;
    setSaving(true);
    try {
      await availabilityApi.setMonthly(doctorId, {
        year,
        month,
        available_dates: dayNumbers,
      });
      addToast("success", "Disponibilidad guardada correctamente");
      onSaved();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Error al guardar la disponibilidad";
      addToast("error", msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel"
        style={{ maxWidth: 480 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Asignar d&iacute;as &mdash; {doctorName}</h2>
          <button
            className="btn-icon"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ marginBottom: 12, color: "#475569", fontSize: "0.9rem" }}>
          Seleccion&aacute; los d&iacute;as que el m&eacute;dico estar&aacute;
          disponible este mes
        </p>

        <div className="av-calendar">
          <DayPicker
            mode="multiple"
            selected={selectedDates}
            onSelect={(dates) => setSelectedDates(dates ?? [])}
            locale={es}
            defaultMonth={now}
            showOutsideDays={false}
          />
        </div>

        <p style={{ marginTop: 12, color: "#334155", fontSize: "0.85rem" }}>
          D&iacute;as seleccionados:{" "}
          {dayNumbers.length > 0
            ? dayNumbers.join(", ")
            : "ninguno"}
        </p>

        <div className="form-footer" style={{ marginTop: 16 }}>
          <button className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={dayNumbers.length === 0 || saving}
          >
            {saving ? "Guardando…" : "Guardar días"}
          </button>
        </div>
      </div>
    </div>
  );
}
