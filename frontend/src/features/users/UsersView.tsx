import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, UserPlus, KeyRound, Pencil, Trash2, Check, X } from "lucide-react";
import { useToast } from "../../components/Toast";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { adminApi, UserRead } from "../../api/admin";

const ROLES = ["encargado", "admin"] as const;

export function UsersView() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<UserRead | null>(null);

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => adminApi.listUsers("encargado"),
  });

  const createMutation = useMutation({
    mutationFn: () => adminApi.createEncargado(newName, newEmail),
    onSuccess: (res) => {
      adminApi.inviteUser(res.user.id).catch(() => {
        addToast("error", "Usuario creado, pero no se pudo enviar la invitación. Verifica la configuración de correo.");
      });
      addToast("success", `Usuario creado. Se ha enviado una invitación a ${newEmail}.`);
      setShowCreate(false);
      setNewName("");
      setNewEmail("");
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => addToast("error", "Error al crear usuario."),
  });

  const resetMutation = useMutation({
    mutationFn: (userId: string) => adminApi.sendReset(userId),
    onSuccess: () => addToast("success", "Correo de restablecimiento enviado."),
    onError: () => addToast("error", "Error al enviar correo de restablecimiento."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { name?: string; role?: string; active?: boolean } }) =>
      adminApi.updateUser(id, payload),
    onSuccess: () => {
      addToast("success", "Usuario actualizado.");
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => addToast("error", "Error al actualizar usuario."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: () => {
      addToast("success", "Usuario eliminado.");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => addToast("error", "Error al eliminar usuario."),
  });

  function startEditing(user: UserRead) {
    setEditingId(user.id);
    setEditName(user.name);
    setEditRole(user.role);
    setEditActive(user.active);
  }

  function cancelEditing() {
    setEditingId(null);
  }

  function saveEditing(userId: string) {
    updateMutation.mutate({
      id: userId,
      payload: { name: editName, role: editRole, active: editActive },
    });
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <ShieldCheck size={20} />
          <h2>Usuarios</h2>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <UserPlus size={15} />
          {showCreate ? "Cancelar" : "Nuevo Usuario"}
        </button>
      </div>

      {showCreate && (
        <div style={{ background: "#f9fafb", padding: "16px", borderRadius: "8px", marginBottom: "20px" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem" }}>Crear Encargado</h4>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label>Nombre <input type="text" value={newName} onChange={e => setNewName(e.target.value)} /></label>
            <label>Email <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} /></label>
            <button className="btn-primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="loading-text">Cargando usuarios…</p>}

      {users && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Nombre</th><th>Email</th><th>Rol</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {users.map(u => (
                editingId === u.id ? (
                  <tr key={u.id} className="edit-row">
                    <td>
                      <input
                        type="text"
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        style={{ width: "100%", boxSizing: "border-box" }}
                      />
                    </td>
                    <td>{u.email}</td>
                    <td>
                      <select value={editRole} onChange={e => setEditRole(e.target.value)}>
                        {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
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
                          onClick={() => saveEditing(u.id)}
                          disabled={updateMutation.isPending}
                        >
                          <Check size={14} /> Guardar
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={cancelEditing}
                        >
                          <X size={14} /> Cancelar
                        </button>
                        <button
                          className="btn-ghost"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => resetMutation.mutate(u.id)}
                        >
                          <KeyRound size={14} /> Resetear
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td>{u.role}</td>
                    <td>
                      {!u.active ? "No" : u.must_change_password ? "Pendiente" : "Activo"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-ghost"
                          style={{ padding: "3px 8px" }}
                          onClick={() => startEditing(u)}
                          title="Editar usuario"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="btn-ghost btn-danger"
                          style={{ padding: "3px 8px" }}
                          onClick={() => setDeleteTarget(u)}
                          title="Eliminar usuario"
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
        title="Eliminar usuario"
        message={`¿Estás seguro de eliminar a ${deleteTarget?.name}?`}
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
