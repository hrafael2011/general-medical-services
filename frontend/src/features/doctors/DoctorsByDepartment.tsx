import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { doctorsApi, DoctorByDepartmentResponse } from "../../api/doctors";

const DEPT_BADGE_COLORS = [
  { bg: "#3b82f6", text: "#fff" },
  { bg: "#8b5cf6", text: "#fff" },
  { bg: "#10b981", text: "#fff" },
  { bg: "#f59e0b", text: "#fff" },
  { bg: "#ef4444", text: "#fff" },
  { bg: "#ec4899", text: "#fff" },
  { bg: "#6366f1", text: "#fff" },
  { bg: "#14b8a6", text: "#fff" },
];
const DEFAULT_DEPT_COLOR = { bg: "#6b7280", text: "#fff" };

function getDepartmentColor(departmentId: string) {
  const hash = departmentId.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return DEPT_BADGE_COLORS[hash % DEPT_BADGE_COLORS.length] || DEFAULT_DEPT_COLOR;
}

export function DoctorsByDepartment() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data, isLoading } = useQuery<DoctorByDepartmentResponse>({
    queryKey: ["doctors", "by-department"],
    queryFn: doctorsApi.listByDepartment,
  });

  if (isLoading) return <p>Cargando...</p>;
  if (!data) return null;

  const deptEntries = Object.entries(data.departments);

  return (
    <div>
      <p className="subtitle" style={{ marginBottom: 20 }}>
        Médicos agrupados por departamento
      </p>

      {deptEntries.map(([deptId, dept]) => {
        const isExpanded = expanded === deptId;
        const badgeColor = getDepartmentColor(deptId);
        const badgeText = dept.label;
        const isEmpty = dept.count === 0;

        if (isEmpty) {
          return (
            <div
              key={deptId}
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
              {dept.label} — Sin médicos asignados
            </div>
          );
        }

        return (
          <div
            key={deptId}
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 10,
              marginBottom: 12,
              overflow: "hidden",
            }}
          >
            <button
              onClick={() => setExpanded(isExpanded ? null : deptId)}
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
                    height: 32,
                    borderRadius: 8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 14,
                    padding: "0 10px",
                    whiteSpace: "nowrap",
                  }}
                >
                  {badgeText}
                </span>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{dept.label}</span>
                  <span style={{ color: "#6b7280", fontSize: 13, marginLeft: 10 }}>
                    {dept.count} médico{dept.count !== 1 ? "s" : ""}
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
                      <th>Estatus</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dept.doctors.map((doc) => (
                      <tr key={doc.id} style={doc.service_active ? undefined : { opacity: 0.75 }}>
                        <td>{doc.name}</td>
                        <td style={{ color: "#6b7280" }}>{doc.rank_name || "Sin rango"}</td>
                        <td style={{ color: "#6b7280" }}>{doc.department_name || "Sin departamento"}</td>
                        <td>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "3px 10px",
                              borderRadius: 9999,
                              fontSize: 12,
                              fontWeight: 600,
                              background: doc.service_active ? "#d1fae5" : "#fee2e2",
                              color: doc.service_active ? "#065f46" : "#991b1b",
                              cursor: !doc.service_active ? "help" : undefined,
                            }}
                            title={!doc.service_active
                              ? `${doc.service_inactive_reason_name || "Sin razón"}${doc.service_inactive_detail ? ` — ${doc.service_inactive_detail}` : ""}`
                              : undefined}
                          >
                            {doc.service_active ? "Activo" : "Inactivo"}
                          </span>
                        </td>
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
