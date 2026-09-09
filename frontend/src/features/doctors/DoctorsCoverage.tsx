import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { doctorsApi } from "../../api/doctors";

const COVERAGE_BADGE_COLORS: Record<string, { bg: string; text: string }> = {
  "3": { bg: "#10b981", text: "#fff" },
  "2": { bg: "#f59e0b", text: "#fff" },
  "1": { bg: "#3b82f6", text: "#fff" },
};
const DEFAULT_BADGE_COLOR = { bg: "#6b7280", text: "#fff" };

export function DoctorsCoverage() {
  const { data: doctorsResp } = useQuery({
    queryKey: ["doctors", "all"],
    queryFn: () => doctorsApi.list("all"),
  });

  const { data: areas } = useQuery({
    queryKey: ["service-areas"],
    queryFn: doctorsApi.listServiceAreas,
  });

  const [expanded, setExpanded] = useState("3");
  const areaMap = Object.fromEntries((areas ?? []).map((a: any) => [a.id, a.display_name]));
  const active = (doctorsResp?.items ?? []).filter((d: any) => d.service_active);

  // Group doctors by area combinations
  const groups: Record<string, { label: string; subtitle: string; subgroups: { title: string; doctors: { id: string; name: string }[] }[] }> = {
    "3": { label: "3 áreas", subtitle: "Emergencia, Pista, Disponible", subgroups: [] },
    "2": { label: "2 áreas", subtitle: "", subgroups: [] },
    "1": { label: "1 área", subtitle: "", subgroups: [] },
  };

  for (const doc of active) {
    const count = doc.allowed_area_ids.length;
    const areasList = doc.allowed_area_ids.map((id: string) => areaMap[id] ?? id).sort();

    if (count >= 3) {
      groups["3"].subgroups.push({ title: "", doctors: [{ id: doc.id, name: doc.name }] });
      continue;
    }

    const key = String(count);
    let sub = groups[key].subgroups.find((s) => s.title === areasList.join(", "));
    if (!sub) {
      sub = { title: areasList.join(", "), doctors: [] };
      groups[key].subgroups.push(sub);
    }
    sub.doctors.push({ id: doc.id, name: doc.name });
  }

  // Sort subgroups and doctors
  for (const key of ["3", "2", "1"]) {
    const g = groups[key];
    if (key === "3") {
      // All 26 doctors in one flat list
      const all = g.subgroups.flatMap((s) => s.doctors);
      all.sort((a, b) => a.name.localeCompare(b.name));
      g.subgroups = [{ title: "", doctors: all }];
    } else {
      g.subgroups.sort((a, b) => a.title.localeCompare(b.title));
      for (const sub of g.subgroups) {
        sub.doctors.sort((a, b) => a.name.localeCompare(b.name));
      }
    }
  }

  // Order: 3 areas first (most), then 1 area, then 2 areas
  const orderedKeys = ["3", "1", "2"];

  return (
    <div>
      <p className="subtitle" style={{ marginBottom: 20 }}>
        Médicos agrupados por cantidad de áreas de cobertura
      </p>

      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        {orderedKeys.map((key) => {
          const total = groups[key].subgroups.reduce((s, g) => s + g.doctors.length, 0);
          return (
            <div key={key} style={{
              flex: 1, padding: "12px 16px", borderRadius: 8,
              background: "#f8fafc", border: "1px solid #e2e8f0",
            }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: "#0f172a" }}>
                {total}
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                {groups[key].label}
              </div>
            </div>
          );
        })}
      </div>

      {orderedKeys.map((key) => {
        const group = groups[key];
        const total = group.subgroups.reduce((s, g) => s + g.doctors.length, 0);
        const isOpen = expanded === key;
        const badgeColor = COVERAGE_BADGE_COLORS[key] || DEFAULT_BADGE_COLOR;
        const badgeText = key;

        if (total === 0) {
          return (
            <div key={key} style={{
              border: "1px dashed #d1d5db", borderRadius: 10,
              padding: 16, textAlign: "center", color: "#9ca3af",
              fontSize: 13, marginBottom: 8,
            }}>
              {group.label} — Sin médicos asignados
            </div>
          );
        }

        return (
          <div key={key} style={{
            border: "1px solid #e5e7eb", borderRadius: 10,
            marginBottom: 12, overflow: "hidden",
          }}>
            <button
              onClick={() => setExpanded(isOpen ? "" : key)}
              style={{
                background: isOpen ? "#f0f9ff" : "#f9fafb",
                padding: "14px 18px",
                display: "flex", alignItems: "center",
                justifyContent: "space-between",
                width: "100%", border: "none", cursor: "pointer",
                borderBottom: isOpen ? "1px solid #e0f2fe" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{
                  background: badgeColor.bg, color: badgeColor.text,
                  width: 32, height: 32, borderRadius: 8,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 700, fontSize: 14,
                }}>
                  {badgeText}
                </span>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{group.label}</span>
                  {key === "3" && <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>— {group.subtitle}</span>}
                  <span style={{ color: "#6b7280", fontSize: 13, marginLeft: 10 }}>
                    {total} médico{total !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 12, color: "#9ca3af" }}>
                {isOpen ? "▲" : "▶"}
              </span>
            </button>

            {isOpen && (
              <div style={{ padding: "12px 18px" }}>
                {group.subgroups.map((sub, i) => (
                  <div key={i}>
                    {sub.title && (
                      <div style={{ fontSize: 12, color: "#475569", fontWeight: 500, margin: "8px 0 4px" }}>
                        {sub.title}
                      </div>
                    )}
                    <div style={{
                      display: "flex", flexWrap: "wrap", gap: 4, padding: "6px 8px",
                      background: "#fafafa", borderRadius: 6,
                    }}>
                      {sub.doctors.map((doc) => (
                        <span key={doc.id} style={{
                          fontSize: 12, padding: "2px 8px", borderRadius: 4,
                          background: "#fff", border: "1px solid #e2e8f0", color: "#334155",
                        }}>
                          {doc.name}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
