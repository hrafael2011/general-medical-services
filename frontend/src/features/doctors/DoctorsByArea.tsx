import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { doctorsApi, DoctorByAreaResponse } from "../../api/doctors";

const AREA_BADGE_COLORS: Record<string, { bg: string; text: string }> = {
  "EMERG": { bg: "#ef4444", text: "#fff" },
  "PISTA": { bg: "#f59e0b", text: "#fff" },
  "DISPONIBLE": { bg: "#10b981", text: "#fff" },
};
const DEFAULT_BADGE_COLOR = { bg: "#6b7280", text: "#fff" };

export function DoctorsByArea() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data, isLoading } = useQuery<DoctorByAreaResponse>({
    queryKey: ["doctors", "by-area"],
    queryFn: doctorsApi.listByArea,
  });

  if (isLoading) return <p>Cargando...</p>;
  if (!data) return null;

  const areaEntries = Object.entries(data.areas);

  return (
    <div>
      <p className="subtitle" style={{ marginBottom: 20 }}>
        Médicos agrupados por área de servicio
      </p>

      {areaEntries.map(([areaId, area]) => {
        const isExpanded = expanded === areaId;
        const badgeColor = AREA_BADGE_COLORS[area.code] || DEFAULT_BADGE_COLOR;
        const badgeText = area.code.slice(0, 2).toUpperCase();
        const isEmpty = area.count === 0;

        if (isEmpty) {
          return (
            <div
              key={areaId}
              style={{
                border: "1px dashed #d1d5db",
                borderRadius: 10,
                padding: 16,
                textAlign: "center",
                color: "#9ca3af",
                fontSize: 13,
                marginBottom: 8,
              }}
            >
              {area.label} — Sin médicos asignados
            </div>
          );
        }

        return (
          <div
            key={areaId}
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 10,
              marginBottom: 12,
              overflow: "hidden",
            }}
          >
            <button
              onClick={() => setExpanded(isExpanded ? null : areaId)}
              style={{
                background: isExpanded ? "#f0f9ff" : "#f9fafb",
                padding: "14px 18px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                border: "none",
                cursor: "pointer",
                borderBottom: isExpanded ? "1px solid #e0f2fe" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span
                  style={{
                    background: badgeColor.bg,
                    color: badgeColor.text,
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 14,
                  }}
                >
                  {badgeText}
                </span>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{area.label}</span>
                  <span style={{ color: "#6b7280", fontSize: 13, marginLeft: 10 }}>
                    {area.count} médico{area.count !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 12, color: "#9ca3af" }}>
                {isExpanded ? "▲" : "▶"}
              </span>
            </button>

            {isExpanded && (
              <div style={{ padding: "12px 18px" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Nombre</th>
                      <th>Rango</th>
                      <th>Departamento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {area.doctors.map((doc) => (
                      <tr key={doc.id}>
                        <td>{doc.name}</td>
                        <td style={{ color: "#6b7280" }}>{doc.rank_name || "Sin rango"}</td>
                        <td style={{ color: "#6b7280" }}>{doc.department_name || "Sin departamento"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
