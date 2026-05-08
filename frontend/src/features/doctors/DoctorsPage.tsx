import { useState } from "react";
import { DoctorList } from "./DoctorList";
import { DoctorForm } from "./DoctorForm";
import { DoctorRead } from "../../api/doctors";

export function DoctorsPage() {
  const [editingDoctor, setEditingDoctor] = useState<DoctorRead | undefined>();
  const [showForm, setShowForm] = useState(false);

  return (
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
  );
}
