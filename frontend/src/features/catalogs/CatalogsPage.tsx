import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, PlusCircle, Pencil, Trash2, Check, X } from "lucide-react";
import { useToast } from "../../components/Toast";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { doctorsApi, RankRead, DepartmentRead, DeactivationReasonRead } from "../../api/doctors";

type Tab = "ranks" | "departments" | "deactivation-reasons";

const TABS: { key: Tab; label: string }[] = [
  { key: "ranks", label: "Rangos" },
  { key: "departments", label: "Departamentos" },
  { key: "deactivation-reasons", label: "Razones de desactivación" },
];

export function CatalogsPage() {
  const [active, setActive] = useState<Tab>("ranks");
  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <BookOpen size={20} />
          <h2>Catálogos</h2>
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

      {active === "ranks" && <RanksTab />}
      {active === "departments" && <DepartmentsTab />}
      {active === "deactivation-reasons" && <DeactivationReasonsTab />}
    </div>
  );
}

function RanksTab() {
  const { addToast } = useToast();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAbbr, setNewAbbr] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editAbbr, setEditAbbr] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<RankRead | null>(null);

  const { data: ranks, isLoading } = useQuery({
    queryKey: ["ranks"],
    queryFn: () => doctorsApi.listRanks(),
  });

  const createMutation = useMutation({
    mutationFn: () => doctorsApi.createRank(newName, newAbbr),
    onSuccess: () => {
      addToast("success", "Rango creado.");
      setShowCreate(false);
      setNewName("");
      setNewAbbr("");
      qc.invalidateQueries({ queryKey: ["ranks"] });
    },
    onError: () => addToast("error", "Error al crear rango."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { name?: string; abbreviation?: string; active?: boolean } }) =>
      doctorsApi.updateRank(id, payload),
    onSuccess: () => {
      addToast("success", "Rango actualizado.");
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ["ranks"] });
    },
    onError: () => addToast("error", "Error al actualizar rango."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => doctorsApi.deleteRank(id),
    onSuccess: () => {
      addToast("success", "Rango eliminado.");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["ranks"] });
    },
    onError: () => addToast("error", "Error al eliminar rango."),
  });

  function startEditing(rank: RankRead) {
    setEditingId(rank.id);
    setEditName(rank.name);
    setEditAbbr(rank.abbreviation);
    setEditActive(true); // RankRead doesn't include active, default to true
  }

  return (
    <div>
      <div style={{ marginBottom: "16px" }}>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <PlusCircle size={15} />
          {showCreate ? "Cancelar" : "Nuevo Rango"}
        </button>
      </div>

      {showCreate && (
        <div style={{ background: "#f9fafb", padding: "16px", borderRadius: "8px", marginBottom: "20px" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem" }}>Crear Rango</h4>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label>Nombre <input type="text" value={newName} onChange={e => setNewName(e.target.value)} /></label>
            <label>Abreviatura <input type="text" value={newAbbr} onChange={e => setNewAbbr(e.target.value)} /></label>
            <button className="btn-primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="loading-text">Cargando rangos…</p>}

      {ranks && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Nombre</th><th>Abreviatura</th><th></th></tr>
            </thead>
            <tbody>
              {ranks.map(r => (
                editingId === r.id ? (
                  <tr key={r.id} className="edit-row">
                    <td>
                      <input
                        type="text"
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        style={{ width: "100%", boxSizing: "border-box" }}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={editAbbr}
                        onChange={e => setEditAbbr(e.target.value)}
                        style={{ width: "100%", boxSizing: "border-box" }}
                      />
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-primary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => updateMutation.mutate({
                            id: r.id,
                            payload: { name: editName, abbreviation: editAbbr },
                          })}
                          disabled={updateMutation.isPending}
                        >
                          <Check size={14} /> Guardar
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => setEditingId(null)}
                        >
                          <X size={14} /> Cancelar
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{r.abbreviation}</td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-ghost"
                          style={{ padding: "3px 8px" }}
                          onClick={() => startEditing(r)}
                          title="Editar rango"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="btn-ghost btn-danger"
                          style={{ padding: "3px 8px" }}
                          onClick={() => setDeleteTarget(r)}
                          title="Eliminar rango"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Eliminar rango"
        message={`¿Estás seguro de eliminar el rango "${deleteTarget?.name}"?`}
        confirmLabel="Sí, eliminar"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

function DepartmentsTab() {
  const { addToast } = useToast();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<DepartmentRead | null>(null);

  const { data: departments, isLoading } = useQuery({
    queryKey: ["departments"],
    queryFn: () => doctorsApi.listDepartments(),
  });

  const createMutation = useMutation({
    mutationFn: () => doctorsApi.createDepartment(newName),
    onSuccess: () => {
      addToast("success", "Departamento creado.");
      setShowCreate(false);
      setNewName("");
      qc.invalidateQueries({ queryKey: ["departments"] });
    },
    onError: () => addToast("error", "Error al crear departamento."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { name?: string; active?: boolean } }) =>
      doctorsApi.updateDepartment(id, payload),
    onSuccess: () => {
      addToast("success", "Departamento actualizado.");
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ["departments"] });
    },
    onError: () => addToast("error", "Error al actualizar departamento."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => doctorsApi.deleteDepartment(id),
    onSuccess: () => {
      addToast("success", "Departamento eliminado.");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["departments"] });
    },
    onError: () => addToast("error", "Error al eliminar departamento."),
  });

  function startEditing(dept: DepartmentRead) {
    setEditingId(dept.id);
    setEditName(dept.name);
    setEditActive(dept.active);
  }

  return (
    <div>
      <div style={{ marginBottom: "16px" }}>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <PlusCircle size={15} />
          {showCreate ? "Cancelar" : "Nuevo Departamento"}
        </button>
      </div>

      {showCreate && (
        <div style={{ background: "#f9fafb", padding: "16px", borderRadius: "8px", marginBottom: "20px" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem" }}>Crear Departamento</h4>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label>Nombre <input type="text" value={newName} onChange={e => setNewName(e.target.value)} /></label>
            <button className="btn-primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="loading-text">Cargando departamentos…</p>}

      {departments && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Nombre</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {departments.map(d => (
                editingId === d.id ? (
                  <tr key={d.id} className="edit-row">
                    <td>
                      <input
                        type="text"
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        style={{ width: "100%", boxSizing: "border-box" }}
                      />
                    </td>
                    <td>
                      <label className="toggle-label" style={{ margin: 0 }}>
                        <input
                          type="checkbox"
                          checked={editActive}
                          onChange={e => setEditActive(e.target.checked)}
                        />
                        {editActive ? "Activo" : "Inactivo"}
                      </label>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-primary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => updateMutation.mutate({
                            id: d.id,
                            payload: { name: editName, active: editActive },
                          })}
                          disabled={updateMutation.isPending}
                        >
                          <Check size={14} /> Guardar
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => setEditingId(null)}
                        >
                          <X size={14} /> Cancelar
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={d.id}>
                    <td>{d.name}</td>
                    <td>{d.active ? "Activo" : "Inactivo"}</td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-ghost"
                          style={{ padding: "3px 8px" }}
                          onClick={() => startEditing(d)}
                          title="Editar departamento"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="btn-ghost btn-danger"
                          style={{ padding: "3px 8px" }}
                          onClick={() => setDeleteTarget(d)}
                          title="Eliminar departamento"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Eliminar departamento"
        message={`¿Estás seguro de eliminar el departamento "${deleteTarget?.name}"?`}
        confirmLabel="Sí, eliminar"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

function DeactivationReasonsTab() {
  const { addToast } = useToast();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newRequiresDetail, setNewRequiresDetail] = useState(false);
  const [newAppliesToSex, setNewAppliesToSex] = useState("");
  const [newSeverity, setNewSeverity] = useState("hard_block");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCode, setEditCode] = useState("");
  const [editName, setEditName] = useState("");
  const [editRequiresDetail, setEditRequiresDetail] = useState(false);
  const [editAppliesToSex, setEditAppliesToSex] = useState("");
  const [editSeverity, setEditSeverity] = useState("hard_block");
  const [editActive, setEditActive] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<DeactivationReasonRead | null>(null);

  const { data: reasons, isLoading } = useQuery({
    queryKey: ["deactivation-reasons"],
    queryFn: () => doctorsApi.listDeactivationReasons(),
  });

  const createMutation = useMutation({
    mutationFn: () => doctorsApi.createDeactivationReason({
      code: newCode,
      display_name: newName,
      requires_detail: newRequiresDetail,
      applies_to_sex: newAppliesToSex || null,
      severity: newSeverity,
    }),
    onSuccess: () => {
      addToast("success", "Razón creada.");
      setShowCreate(false);
      setNewCode("");
      setNewName("");
      setNewRequiresDetail(false);
      setNewAppliesToSex("");
      setNewSeverity("hard_block");
      qc.invalidateQueries({ queryKey: ["deactivation-reasons"] });
    },
    onError: () => addToast("error", "Error al crear razón."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<{
      code: string;
      display_name: string;
      requires_detail: boolean;
      applies_to_sex: string | null;
      severity: string;
      active: boolean;
    }> }) => doctorsApi.updateDeactivationReason(id, payload),
    onSuccess: () => {
      addToast("success", "Razón actualizada.");
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ["deactivation-reasons"] });
    },
    onError: () => addToast("error", "Error al actualizar razón."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => doctorsApi.deleteDeactivationReason(id),
    onSuccess: () => {
      addToast("success", "Razón desactivada.");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["deactivation-reasons"] });
    },
    onError: () => addToast("error", "Error al desactivar razón."),
  });

  function startEditing(reason: DeactivationReasonRead) {
    setEditingId(reason.id);
    setEditCode(reason.code);
    setEditName(reason.display_name);
    setEditRequiresDetail(reason.requires_detail);
    setEditAppliesToSex(reason.applies_to_sex ?? "");
    setEditSeverity(reason.severity);
    setEditActive(reason.active);
  }

  return (
    <div>
      <div style={{ marginBottom: "16px" }}>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <PlusCircle size={15} />
          {showCreate ? "Cancelar" : "Nueva Razón"}
        </button>
      </div>

      {showCreate && (
        <div style={{ background: "#f9fafb", padding: "16px", borderRadius: "8px", marginBottom: "20px" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem" }}>Crear razón de desactivación</h4>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label>Código <input type="text" value={newCode} onChange={e => setNewCode(e.target.value)} /></label>
            <label>Nombre visible <input type="text" value={newName} onChange={e => setNewName(e.target.value)} /></label>
            <label>
              Aplica a sexo
              <select value={newAppliesToSex} onChange={e => setNewAppliesToSex(e.target.value)}>
                <option value="">Todos</option>
                <option value="male">Masculino</option>
                <option value="female">Femenino</option>
              </select>
            </label>
            <label>
              Severidad
              <select value={newSeverity} onChange={e => setNewSeverity(e.target.value)}>
                <option value="hard_block">Bloquea servicio</option>
                <option value="warn">Advertencia</option>
              </select>
            </label>
            <label className="toggle-label" style={{ margin: 0 }}>
              <input
                type="checkbox"
                checked={newRequiresDetail}
                onChange={e => setNewRequiresDetail(e.target.checked)}
              />
              Requiere detalle
            </label>
            <button className="btn-primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="loading-text">Cargando razones…</p>}

      {reasons && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Nombre</th><th>Código</th><th>Sexo</th><th>Severidad</th><th>Detalle</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {reasons.map(reason => (
                editingId === reason.id ? (
                  <tr key={reason.id} className="edit-row">
                    <td>
                      <input type="text" value={editName} onChange={e => setEditName(e.target.value)} style={{ width: "100%", boxSizing: "border-box" }} />
                    </td>
                    <td>
                      <input type="text" value={editCode} onChange={e => setEditCode(e.target.value)} style={{ width: "100%", boxSizing: "border-box" }} />
                    </td>
                    <td>
                      <select value={editAppliesToSex} onChange={e => setEditAppliesToSex(e.target.value)}>
                        <option value="">Todos</option>
                        <option value="male">Masculino</option>
                        <option value="female">Femenino</option>
                      </select>
                    </td>
                    <td>
                      <select value={editSeverity} onChange={e => setEditSeverity(e.target.value)}>
                        <option value="hard_block">Bloquea servicio</option>
                        <option value="warn">Advertencia</option>
                      </select>
                    </td>
                    <td>
                      <label className="toggle-label" style={{ margin: 0 }}>
                        <input type="checkbox" checked={editRequiresDetail} onChange={e => setEditRequiresDetail(e.target.checked)} />
                        {editRequiresDetail ? "Sí" : "No"}
                      </label>
                    </td>
                    <td>
                      <label className="toggle-label" style={{ margin: 0 }}>
                        <input type="checkbox" checked={editActive} onChange={e => setEditActive(e.target.checked)} />
                        {editActive ? "Activo" : "Inactivo"}
                      </label>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-primary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => updateMutation.mutate({
                            id: reason.id,
                            payload: {
                              code: editCode,
                              display_name: editName,
                              requires_detail: editRequiresDetail,
                              applies_to_sex: editAppliesToSex || null,
                              severity: editSeverity,
                              active: editActive,
                            },
                          })}
                          disabled={updateMutation.isPending}
                        >
                          <Check size={14} /> Guardar
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => setEditingId(null)}
                        >
                          <X size={14} /> Cancelar
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={reason.id}>
                    <td>{reason.display_name}</td>
                    <td>{reason.code}</td>
                    <td>{sexLabel(reason.applies_to_sex)}</td>
                    <td>{severityLabel(reason.severity)}</td>
                    <td>{reason.requires_detail ? "Sí" : "No"}</td>
                    <td>{reason.active ? "Activo" : "Inactivo"}</td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-ghost"
                          style={{ padding: "3px 8px" }}
                          onClick={() => startEditing(reason)}
                          title="Editar razón"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="btn-ghost btn-danger"
                          style={{ padding: "3px 8px" }}
                          onClick={() => setDeleteTarget(reason)}
                          title="Desactivar razón"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Desactivar razón"
        message={`¿Estás seguro de desactivar la razón "${deleteTarget?.display_name}"?`}
        confirmLabel="Sí, desactivar"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

function sexLabel(value: string | null): string {
  if (value === "male") return "Masculino";
  if (value === "female") return "Femenino";
  return "Todos";
}

function severityLabel(value: string): string {
  return value === "hard_block" ? "Bloquea servicio" : "Advertencia";
}
