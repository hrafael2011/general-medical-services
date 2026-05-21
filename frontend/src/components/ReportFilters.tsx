import { ReactNode } from "react";

interface FilterProps {
  children: ReactNode;
}

export function ReportFilters({ children }: FilterProps) {
  return (
    <div
      className="audit-filters"
      style={{ marginBottom: "24px", display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}
    >
      {children}
    </div>
  );
}

interface FilterLabelProps {
  label: string;
  children: ReactNode;
}

export function FilterLabel({ label, children }: FilterLabelProps) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.8rem", color: "#374151" }}>
      {label}
      {children}
    </label>
  );
}

interface ActionButtonsProps {
  onSearch: () => void;
  onPdf?: () => void;
  onExcel?: () => void;
  loading?: boolean;
}

export function ActionButtons({ onSearch, onPdf, onExcel, loading }: ActionButtonsProps) {
  return (
    <div style={{ display: "flex", gap: "8px", alignItems: "flex-end" }}>
      <button className="btn-primary" onClick={onSearch} disabled={loading}>
        {loading ? "Cargando…" : "Aplicar"}
      </button>
      {onPdf && <button className="btn-ghost" onClick={onPdf}>PDF</button>}
      {onExcel && <button className="btn-ghost" onClick={onExcel}>Excel</button>}
    </div>
  );
}
