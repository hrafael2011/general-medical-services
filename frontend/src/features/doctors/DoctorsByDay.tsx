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

  const { data: doctorsResp } = useQuery({
    queryKey: ["doctors", "all"],
    queryFn: () => doctorsApi.list("all"),
  });

  if (isLoading) return <p>Cargando...</p>;
  if (!data) return null;

  const active = (doctorsResp?.items ?? []).filter((d: any) => d.service_active);

  // Monthly doctors (avisan sus días)
  const monthlyDoctors = active.filter((d: any) => d.availability_mode === "monthly");

  // Recurring doctor IDs (una vez al mes)
  const recurringIds = new Set<string>();
  const recurringDoctors: { id: string; name: string; tag: string }[] = [];
  for (const items of Object.values(data.days)) {
    for (const doc of (items as any).doctors ?? []) {
      if (doc.recurring_tag && !recurringIds.has(doc.id)) {
        recurringIds.add(doc.id);
        recurringDoctors.push({ id: doc.id, name: doc.name, tag: doc.recurring_tag });
      }
    }
  }
  recurringDoctors.sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div>
      {/* Section 1: Fixed weekday */}
      <h3 style={{ margin: "20px 0 12px", fontSize: 15, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 18 }}>📅</span> Días fijos de semana
        <span className="count-badge">{Object.values(data.days).reduce((s, d) => s + d.doctors.filter(doc => !doc.recurring_tag).length, 0)}</span>
      </h3>

      {DAY_KEYS.map((key) => {
        const day = data.days[key];
        const fixedDoctors = day.doctors.filter((d) => !d.recurring_tag);
        const isExpanded = expanded === key;
        const badgeColor = DAY_BADGE_COLORS[key];
        const isEmpty = fixedDoctors.length === 0;

        if (isEmpty) {
          return (
            <div key={key} style={{
              border: "1px dashed #d1d5db", borderRadius: 10, padding: 16,
              textAlign: "center", color: "#9ca3af", fontSize: 13, marginBottom: 8,
            }}>
              {day.label} — Sin médicos asignados
            </div>
          );
        }

        return (
          <div key={key} style={{
            border: "1px solid #e5e7eb", borderRadius: 10, marginBottom: 12, overflow: "hidden",
          }}>
            <button
              onClick={() => setExpanded(isExpanded ? null : key)}
              style={{
                background: isExpanded ? "#f0f9ff" : "#f9fafb", padding: "14px 18px",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                width: "100%", border: "none", cursor: "pointer",
                borderBottom: isExpanded ? "1px solid #e0f2fe" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{
                  background: badgeColor.bg, color: badgeColor.text,
                  width: 32, height: 32, borderRadius: 8,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 700, fontSize: 14,
                }}>
                  {DAY_BADGES[key]}
                </span>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{day.label}</span>
                  <span style={{ color: "#6b7280", fontSize: 13, marginLeft: 10 }}>
                    {fixedDoctors.length} médico{fixedDoctors.length !== 1 ? "s" : ""}
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
                      <th>WhatsApp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fixedDoctors.map((doc) => (
                      <tr key={doc.id}>
                        <td>{doc.name}</td>
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

      {/* Section 2: Monthly variable */}
      {monthlyDoctors.length > 0 && (
        <>
          <h3 style={{ margin: "20px 0 12px", fontSize: 15, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 18 }}>📋</span> Avisan sus días
            <span className="count-badge">{monthlyDoctors.length}</span>
          </h3>
          <div style={{
            border: "1px solid #e5e7eb", borderRadius: 10, padding: "14px 18px",
            background: "#fafafa", display: "flex", flexWrap: "wrap", gap: 6,
          }}>
            {monthlyDoctors.map((doc: any) => (
              <span key={doc.id} style={{
                fontSize: 13, padding: "4px 10px", borderRadius: 6,
                background: "#fff", border: "1px solid #e2e8f0", color: "#334155",
              }}>
                {doc.name}
              </span>
            ))}
          </div>
        </>
      )}

      {/* Section 3: Recurring */}
      {recurringDoctors.length > 0 && (
        <>
          <h3 style={{ margin: "20px 0 12px", fontSize: 15, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 18 }}>🔄</span> Una vez al mes
            <span className="count-badge">{recurringDoctors.length}</span>
          </h3>
          <div style={{
            border: "1px solid #e5e7eb", borderRadius: 10, padding: "14px 18px",
            background: "#fafafa", display: "flex", flexDirection: "column", gap: 6,
          }}>
            {recurringDoctors.map((doc) => (
              <div key={doc.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <span style={{ color: "#334155" }}>{doc.name}</span>
                <span style={{
                  background: "#fef3c7", color: "#92400e", fontSize: 11,
                  padding: "2px 8px", borderRadius: 4, fontWeight: 500,
                }}>
                  {doc.tag}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

    </div>
  );
}
