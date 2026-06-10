import { useState } from "react";
import { DoctorList } from "./DoctorList";
import { DoctorForm } from "./DoctorForm";
import { DoctorsByDay } from "./DoctorsByDay";
import { DoctorsByArea } from "./DoctorsByArea";
import { DoctorRead } from "../../api/doctors";
import { useAuth } from "../../context/AuthContext";

type Tab = "list" | "by-day" | "by-area";

export function DoctorsPage() {
  const [editingDoctor, setEditingDoctor] = useState<DoctorRead | undefined>();
  const [showForm, setShowForm] = useState(false);
  const [tab, setTab] = useState<Tab>("list");
  const { currentUser } = useAuth();
  const isEncargadoPlus = currentUser && (currentUser.role === "encargado" || currentUser.role === "admin");

  return (
    <>
      <div className="feature-panel">
        <div className="feature-header">
          <h2>Médicos</h2>
        </div>

        <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #e5e7eb", marginBottom: 20 }}>
          <button
            className={tab === "list" ? "btn-primary" : "btn-ghost"}
            style={{ padding: "8px 16px", borderRadius: "6px 6px 0 0", border: "none", fontSize: 13 }}
            onClick={() => setTab("list")}
          >
            Lista
          </button>
          {isEncargadoPlus && (
            <button
              className={tab === "by-day" ? "btn-primary" : "btn-ghost"}
              style={{ padding: "8px 16px", borderRadius: "6px 6px 0 0", border: "none", fontSize: 13 }}
              onClick={() => setTab("by-day")}
            >
              Por Día
            </button>
          )}
          {isEncargadoPlus && (
            <button
              className={tab === "by-area" ? "btn-primary" : "btn-ghost"}
              style={{ padding: "8px 16px", borderRadius: "6px 6px 0 0", border: "none", fontSize: 13 }}
              onClick={() => setTab("by-area")}
            >
              Por Área
            </button>
          )}
        </div>

        {tab === "list" ? (
          <>
            <DoctorList
              onAdd={() => { setEditingDoctor(undefined); setShowForm(true); }}
              onEdit={doc => { setEditingDoctor(doc); setShowForm(true); }}
            />
            {showForm && (
              <DoctorForm
                doctor={editingDoctor}
                onClose={() => { setShowForm(false); setEditingDoctor(undefined); }}
              />
            )}
          </>
        ) : tab === "by-day" ? (
          <DoctorsByDay />
        ) : (
          <DoctorsByArea />
        )}
      </div>
    </>
  );
}
