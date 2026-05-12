import { useState } from "react";
import { Search } from "lucide-react";
import { DoctorRead } from "../../api/doctors";

const MONTHS = ["enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"];

interface Props {
  date: string;          // "2026-05-03"
  areaName: string;
  doctors: DoctorRead[];
  currentDoctorId?: string;
  availableDoctorIds?: string[];
  onConfirm: (doctorId: string) => void;
  onClose: () => void;
  isLoading: boolean;
  onRemove?: () => void;
}

export function AssignDoctorModal({ date, areaName, doctors, currentDoctorId, availableDoctorIds, onConfirm, onClose, isLoading, onRemove }: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(currentDoctorId ?? null);

  const [year, month, day] = date.split("-").map(Number);
  const title = `${day} de ${MONTHS[month - 1]} ${year} · ${areaName}`;

  const filtered = doctors.filter(d => {
    if (!d.name.toLowerCase().includes(query.toLowerCase())) return false;
    if (availableDoctorIds && d.id !== currentDoctorId) {
      return availableDoctorIds.includes(d.id);
    }
    return true;
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" style={{ maxWidth: 480 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Asignar — {title}</h2>
          <button className="btn-icon" onClick={onClose} aria-label="Cerrar">×</button>
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

        <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
          {filtered.length === 0 && (
            <p style={{ padding: "12px 16px", color: "#94a3b8", fontSize: "0.88rem" }}>Sin resultados.</p>
          )}
          {filtered.map(doc => {
            const isCurrent = doc.id === currentDoctorId;
            return (
              <button
                key={doc.id}
                onClick={() => !isCurrent && setSelectedId(doc.id)}
                style={{
                  width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "10px 16px",
                  background: isCurrent ? "#f1f5f9" : selectedId === doc.id ? "#bfdbfe" : "transparent",
                  border: 0, borderBottom: "1px solid #f1f5f9", cursor: isCurrent ? "default" : "pointer",
                  textAlign: "left", fontSize: "0.9rem", opacity: isCurrent ? 0.6 : 1,
                }}
              >
                <span style={{ fontWeight: selectedId === doc.id ? 700 : 400, color: "#1e293b" }}>{doc.name}</span>
                <span style={{ fontSize: "0.78rem", color: isCurrent ? "#94a3b8" : doc.service_active ? "#166534" : "#b91c1c" }}>
                  {isCurrent ? "◉ Asignado" : doc.service_active ? "✓ activo" : "✗ inactivo"}
                </span>
              </button>
            );
          })}
        </div>

        <div className="form-footer" style={{ marginTop: 16 }}>
          <button className="btn-secondary" onClick={onClose}>Cancelar</button>
          {onRemove && (
            <button className="btn-secondary" onClick={onRemove} style={{ marginRight: "auto", color: "#b91c1c", borderColor: "#fecaca" }}>
              Quitar asignación
            </button>
          )}
          <button
            className="btn-primary"
            onClick={() => selectedId && onConfirm(selectedId)}
            disabled={!selectedId || selectedId === currentDoctorId || isLoading}
          >
            {isLoading ? "Asignando…" : "Asignar"}
          </button>
        </div>
      </div>
    </div>
  );
}
