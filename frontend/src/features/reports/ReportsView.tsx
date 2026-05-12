import { useState } from "react";
import { BarChart2 } from "lucide-react";
import { CoverageReport } from "./CoverageReport";
import { WorkloadReport } from "./WorkloadReport";
import { DoctorDossierReport } from "./DoctorDossierReport";

type Tab = "coverage" | "workload" | "dossier";

const TABS: { key: Tab; label: string }[] = [
  { key: "coverage", label: "Cobertura y Brechas" },
  { key: "workload", label: "Carga de Trabajo" },
  { key: "dossier", label: "Ficha Individual" },
];

export function ReportsView() {
  const [active, setActive] = useState<Tab>("coverage");

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <BarChart2 size={20} />
          <h2>Reportes</h2>
        </div>
      </div>

      <div style={{ display: "flex", gap: "8px", marginBottom: "24px", borderBottom: "1px solid #e5e7eb", paddingBottom: "8px" }}>
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={active === tab.key ? "btn-primary" : "btn-ghost"}
            onClick={() => setActive(tab.key)}
            style={{ fontSize: "0.85rem" }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {active === "coverage" && <CoverageReport />}
      {active === "workload" && <WorkloadReport />}
      {active === "dossier" && <DoctorDossierReport />}
    </div>
  );
}
