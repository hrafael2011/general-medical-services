const MONTHS = ["enero","febrero","marzo","abril","mayo","junio",
                 "julio","agosto","septiembre","octubre","noviembre","diciembre"];

interface Props {
  doctorName: string;
  date: string;       // "2026-05-03"
  areaName: string;
  source: string;     // "generated" | "manual"
  onConfirm: () => void;
  onClose: () => void;
  isLoading: boolean;
}

export function RemoveAssignmentPopover({ doctorName, date, areaName, source, onConfirm, onClose, isLoading }: Props) {
  const [year, month, day] = date.split("-").map(Number);
  const subtitle = `${day} de ${MONTHS[month - 1]} ${year} · ${areaName}`;
  const sourceLabel = source === "generated" ? "Asignado automáticamente" : "Asignado manualmente";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ fontSize: "1rem" }}>Quitar asignación</h2>
          <button className="btn-icon" onClick={onClose} aria-label="Cerrar">×</button>
        </div>
        <p style={{ margin: "0 0 4px", fontWeight: 700 }}>{doctorName}</p>
        <p style={{ margin: "0 0 8px", fontSize: "0.88rem", color: "#475569" }}>{subtitle}</p>
        <p style={{ margin: "0 0 20px", fontSize: "0.82rem", color: "#94a3b8" }}>{sourceLabel}</p>
        <div className="form-footer">
          <button className="btn-secondary" onClick={onClose}>Cancelar</button>
          <button
            className="btn-primary"
            style={{ background: "#b91c1c" }}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? "Quitando…" : "Quitar asignación"}
          </button>
        </div>
      </div>
    </div>
  );
}
