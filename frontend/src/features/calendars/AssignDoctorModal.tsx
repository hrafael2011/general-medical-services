import { useState } from "react";
import { Search } from "lucide-react";
import { DoctorRead } from "../../api/doctors";

const MONTHS = ["enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"];

interface Props {
  date: string;          // "2026-05-03"
  areaName: string;
  doctors: DoctorRead[];
  onConfirm: (doctorId: string) => void;
  onClose: () => void;
  isLoading: boolean;
}

export function AssignDoctorModal({ date, areaName, doctors, onConfirm, onClose, isLoading }: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [year, month, day] = date.split("-").map(Number);
  const title = `${day} de ${MONTHS[month - 1]} ${year} · ${areaName}`;

  const filtered = doctors.filter(d =>
    d.name.toLowerCase().includes(query.toLowerCase())
  );

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
          {filtered.map(doc => (
            <button
              key={doc.id}
              onClick={() => setSelectedId(doc.id)}
              style={{
                width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "10px 16px", background: selectedId === doc.id ? "#e0f2fe" : "transparent",
                border: 0, borderBottom: "1px solid #f1f5f9", cursor: "pointer", textAlign: "left",
                fontSize: "0.9rem",
              }}
            >
              <span style={{ fontWeight: selectedId === doc.id ? 700 : 400 }}>{doc.name}</span>
              <span style={{ fontSize: "0.78rem", color: doc.service_active ? "#166534" : "#b91c1c" }}>
                {doc.service_active ? "✓ activo" : "✗ inactivo"}
              </span>
            </button>
          ))}
        </div>

        <div className="form-footer" style={{ marginTop: 16 }}>
          <button className="btn-secondary" onClick={onClose}>Cancelar</button>
          <button
            className="btn-primary"
            onClick={() => selectedId && onConfirm(selectedId)}
            disabled={!selectedId || isLoading}
          >
            {isLoading ? "Asignando…" : "Asignar"}
          </button>
        </div>
      </div>
    </div>
  );
}
