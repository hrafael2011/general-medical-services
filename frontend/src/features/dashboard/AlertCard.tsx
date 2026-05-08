import { useNavigate } from "react-router-dom";

type Severity = "warning" | "success" | "info";

interface Props {
  severity: Severity;
  icon: string;
  title: string;
  detail?: string;
  actionLabel?: string;
  actionTo?: string;
}

export function AlertCard({ severity, icon, title, detail, actionLabel, actionTo }: Props) {
  const navigate = useNavigate();
  return (
    <div className={`alert-card alert-card-${severity}`}>
      <span className="alert-card-icon">{icon}</span>
      <div className="alert-card-body">
        <p className="alert-card-title">{title}</p>
        {detail && <p className="alert-card-detail">{detail}</p>}
      </div>
      {actionLabel && actionTo && (
        <button className="btn-primary" style={{ fontSize: "0.82rem", minHeight: 30 }} onClick={() => navigate(actionTo)}>
          {actionLabel} →
        </button>
      )}
    </div>
  );
}
