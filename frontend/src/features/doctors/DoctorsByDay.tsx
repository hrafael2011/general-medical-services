import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { doctorsApi, DoctorByDayResponse } from "../../api/doctors";

const DAY_KEYS = ["0", "1", "2", "3", "4", "5", "6"];
const DAY_BADGES: Record<string, string> = {
  "0": "L", "1": "M", "2": "X", "3": "J", "4": "V", "5": "S", "6": "D",
};
const DAY_BADGE_COLORS: Record<string, { bg: string; text: string }> = {
  "0": { bg: "#3b82f6", text: "#fff" },
  "1": { bg: "#8b5cf6", text: "#fff" },
  "2": { bg: "#10b981", text: "#fff" },
  "3": { bg: "#f59e0b", text: "#fff" },
  "4": { bg: "#ef4444", text: "#fff" },
  "5": { bg: "#6366f1", text: "#fff" },
  "6": { bg: "#ec4899", text: "#fff" },
};

export function DoctorsByDay() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data, isLoading } = useQuery<DoctorByDayResponse>({
    queryKey: ["doctors", "by-day"],
    queryFn: doctorsApi.listByDay,
  });

  if (isLoading) return <p>Cargando...</p>;
  if (!data) return null;

  return (
    <div>
      <p className="subtitle" style={{ marginBottom: 20 }}>
        Médicos agrupados por día de la semana — solo disponibilidad fija y recurrente
      </p>

      {DAY_KEYS.map((key) => {
        const day = data.days[key];
        const isExpanded = expanded === key;
        const badgeColor = DAY_BADGE_COLORS[key];
        const isEmpty = day.count === 0;

        if (isEmpty) {
          return (
            <div
              key={key}
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
              {day.label} — Sin médicos asignados
            </div>
          );
        }

        return (
          <div
            key={key}
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 10,
              marginBottom: 12,
              overflow: "hidden",
            }}
          >
            <button
              onClick={() => setExpanded(isExpanded ? null : key)}
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
                  {DAY_BADGES[key]}
                </span>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{day.label}</span>
                  <span style={{ color: "#6b7280", fontSize: 13, marginLeft: 10 }}>
                    {day.count} médico{day.count !== 1 ? "s" : ""}
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
                      <th>Teléfono</th>
                    </tr>
                  </thead>
                  <tbody>
                    {day.doctors.map((doc) => (
                      <tr key={doc.id}>
                        <td>
                          {doc.name}
                          {doc.recurring_tag && (
                            <span
                              style={{
                                background: "#fef3c7",
                                color: "#92400e",
                                fontSize: 10,
                                padding: "2px 6px",
                                borderRadius: 4,
                                marginLeft: 6,
                                fontWeight: 500,
                              }}
                            >
                              ({doc.recurring_tag})
                            </span>
                          )}
                        </td>
                        <td style={{ color: "#6b7280" }}>{doc.rank_name || "Sin rango"}</td>
                        <td style={{ color: "#6b7280" }}>{doc.department_name || "Sin departamento"}</td>
                        <td style={{ color: "#6b7280" }}>{doc.whatsapp_phone || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}

      {/* Legend */}
      <div
        style={{
          marginTop: 20,
          padding: "12px 16px",
          background: "#f9fafb",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          gap: 12,
          fontSize: 12,
        }}
      >
        <span style={{ background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: 4, fontWeight: 500 }}>
          (patrón recurrente)
        </span>
        <span style={{ color: "#6b7280" }}>Médico con un solo servicio al mes (último viernes, primer jueves, etc.)</span>
      </div>
    </div>
  );
}
