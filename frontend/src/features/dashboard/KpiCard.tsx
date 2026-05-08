interface Props { value: string | number; label: string; }

export function KpiCard({ value, label }: Props) {
  return (
    <div className="kpi-card">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
