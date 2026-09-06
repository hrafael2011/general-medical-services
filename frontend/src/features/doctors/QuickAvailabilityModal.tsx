import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { DayPicker } from "react-day-picker";
import { useQuery } from "@tanstack/react-query";
import { es } from "date-fns/locale";
import { format } from "date-fns";
import "react-day-picker/style.css";
import { availabilityApi } from "../../api/doctors";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";

interface Props {
  doctorId: string;
  doctorName: string;
  onClose: () => void;
  onSaved: () => void;
}

export function QuickAvailabilityModal({ doctorId, doctorName, onClose, onSaved }: Props) {
  const { addToast } = useToast();
  const [saving, setSaving] = useState(false);
  // Mes visible en el calendario: por defecto el actual, pero el encargado
  // puede navegar a otros meses (anteriores incluidos) para asignar/corregir.
  const [viewDate, setViewDate] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDates, setSelectedDates] = useState<Date[]>([]);
  const viewYear = viewDate.getFullYear();
  const viewMonth = viewDate.getMonth() + 1; // JS months are 0-indexed

  // Carga la disponibilidad del médico y preselecciona los días guardados del
  // mes visible: el guardado y la preselección SIEMPRE apuntan al mes que el
  // usuario está viendo (antes se hardcodeaba el mes actual y los días
  // elegidos en otro mes se guardaban en el mes equivocado).
  const { data: availability } = useQuery({
    queryKey: ["doctor-availability", doctorId],
    queryFn: () => availabilityApi.list(doctorId),
  });

  const appliedMonthRef = useRef<string | null>(null);
  useEffect(() => {
    if (!availability) return;
    const viewKey = `${viewYear}-${viewMonth}`;
    if (appliedMonthRef.current === viewKey) return;
    appliedMonthRef.current = viewKey;
    const saved = availability.find(
      (a) => a.availability_type === "monthly_variable" && a.year === viewYear && a.month === viewMonth,
    );
    setSelectedDates(
      saved?.available_dates?.length
        ? saved.available_dates.map((day) => new Date(viewYear, viewMonth - 1, day))
        : [],
    );
  }, [availability, viewYear, viewMonth]);

  const dayNumbers = selectedDates
    .map((d) => d.getDate())
    .sort((a, b) => a - b);

  const monthLabel = format(viewDate, "MMMM yyyy", { locale: es });

  const handleSave = async () => {
    if (dayNumbers.length === 0) return;
    setSaving(true);
    try {
      await availabilityApi.setMonthly(doctorId, {
        year: viewYear,
        month: viewMonth,
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
          disponible en {monthLabel}
        </p>

        <div className="av-calendar">
          <DayPicker
            mode="multiple"
            month={viewDate}
            onMonthChange={(month) => setViewDate(month)}
            selected={selectedDates}
            onSelect={(dates) => setSelectedDates(dates ?? [])}
            locale={es}
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
