import { useState, Fragment } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, UserPlus, KeyRound, Pencil, Trash2, Check, X } from "lucide-react";
import { useToast } from "../../components/Toast";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useAuth } from "../../context/AuthContext";
import { adminApi, UserRead } from "../../api/admin";

const ROLES = ["encargado", "admin"] as const;

const PERMISSION_GROUPS = [
  {
    category: "Gestión Médica",
    permissions: [
      { key: "manage_doctors", label: "Gestionar Médicos" },
      { key: "manage_availability", label: "Gestionar Disponibilidad" },
      { key: "manage_missions", label: "Gestionar Misiones" },
    ],
  },
  {
    category: "Calendarios",
    permissions: [
      { key: "manage_calendars", label: "Gestionar Calendarios" },
      { key: "manage_confirmations", label: "Gestionar Confirmaciones" },
    ],
  },
  {
    category: "Administración",
    permissions: [
      { key: "manage_users", label: "Gestionar Usuarios" },
      { key: "manage_trash", label: "Gestionar Papelera" },
      { key: "manage_catalogs", label: "Gestionar Catálogos" },
      { key: "manage_admins", label: "Gestionar Administradores" },
    ],
  },
  {
    category: "Monitoreo",
    permissions: [
      { key: "view_audit", label: "Ver Auditoría" },
      { key: "view_notifications", label: "Ver Notificaciones" },
      { key: "manage_alerts", label: "Gestionar Alertas" },
      { key: "receive_escalation_alerts", label: "Recibir Alertas de Escalamiento" },
    ],
  },
  {
    category: "Reportes",
    permissions: [
      { key: "export_reports", label: "Exportar Reportes" },
    ],
  },
];

export function UsersView() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const { currentUser } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPermissions, setNewPermissions] = useState<string[]>([]);
  const [newRole, setNewRole] = useState<string>("encargado");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [editPermissions, setEditPermissions] = useState<string[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<UserRead | null>(null);

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: async (): Promise<UserRead[]> => {
      const roles = currentUser?.is_superadmin
        ? ["encargado", "admin"]
        : ["encargado"];
      const usersByRole = await Promise.all(
        roles.map((role) => adminApi.listUsers(role))
      );
      return usersByRole.flat().sort((a, b) => a.name.localeCompare(b.name));
    },
  });

  const createMutation = useMutation({
    mutationFn: () => adminApi.createEncargado(newName, newEmail, undefined, newPermissions),
    onSuccess: (res) => {
      adminApi.inviteUser(res.user.id).catch(() => {
        addToast("error", "Usuario creado, pero no se pudo enviar la invitación. Verifica la configuración de correo.");
      });
      addToast("success", `Usuario creado. Se ha enviado una invitación a ${newEmail}.`);
      setShowCreate(false);
      setNewName("");
      setNewEmail("");
      setNewPermissions([]);
      setNewRole("encargado");
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : "Error al crear usuario.";
      addToast("error", message || "Error al crear usuario.");
    },
  });

  const createAdminMutation = useMutation({
    mutationFn: () => adminApi.createAdmin(newName, newEmail),
    onSuccess: (res) => {
      adminApi.inviteUser(res.user.id).catch(() => {
        addToast("error", "Administrador creado, pero no se pudo enviar la invitación.");
      });
      addToast("success", `Administrador creado. Invitación enviada a ${newEmail}.`);
      setShowCreate(false);
      setNewName("");
      setNewEmail("");
      setNewPermissions([]);
      setNewRole("encargado");
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err) => {
      addToast("error", err instanceof Error ? err.message : "Error al crear administrador.");
    },
  });

  const resetMutation = useMutation({
    mutationFn: (userId: string) => adminApi.sendReset(userId),
    onSuccess: () => addToast("success", "Correo de restablecimiento enviado."),
    onError: (err: Error) => addToast("error", err.message || "Error al enviar correo de restablecimiento."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { name?: string; role?: string; active?: boolean; permissions?: string[] } }) =>
      adminApi.updateUser(id, payload),
    onSuccess: () => {
      addToast("success", "Usuario actualizado.");
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err: Error) => addToast("error", err.message || "Error al actualizar usuario."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: () => {
      addToast("success", "Usuario eliminado.");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err: Error) => addToast("error", err.message || "Error al eliminar usuario."),
  });

  function startEditing(user: UserRead) {
    setEditingId(user.id);
    setEditName(user.name);
    setEditRole(user.role);
    setEditActive(user.active);
    setEditPermissions(user.permissions ?? []);
  }

  function cancelEditing() {
    setEditingId(null);
  }

  function saveEditing(userId: string) {
    updateMutation.mutate({
      id: userId,
      payload: { name: editName, role: editRole, active: editActive, permissions: editPermissions },
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
          {/* Title */}
          <h4 style={{ margin: "0 0 12px", fontSize: "1rem" }}>
            Crear {newRole === "admin" ? "Administrador" : "Encargado"}
          </h4>

          {/* Name + Email */}
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label>Nombre <input type="text" value={newName} onChange={e => setNewName(e.target.value)} /></label>
            <label>Email <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} /></label>
          </div>

          {/* Role selector */}
          <div className="form-section">
            <h4 className="form-section-title">Rol</h4>
            <p className="form-section-desc">Define el nivel de acceso del usuario</p>
            <div className="role-cards">
              <div
                className={`role-card${newRole === "encargado" ? " role-card--active" : ""}`}
                onClick={() => setNewRole("encargado")}
              >
                <div className="role-card-radio">
                  <div className="role-card-radio-dot" />
                </div>
                <div>
                  <div className="role-card-title">Encargado</div>
                  <div className="role-card-desc">Acceso con permisos específicos</div>
                </div>
              </div>
              <div
                className={`role-card${newRole === "admin" ? " role-card--active" : ""}${!currentUser?.is_superadmin ? " role-card--disabled" : ""}`}
                onClick={() => { if (currentUser?.is_superadmin) setNewRole("admin"); }}
              >
                <div className="role-card-radio">
                  <div className="role-card-radio-dot" />
                </div>
                <div>
                  <div className="role-card-title">Administrador</div>
                  <div className="role-card-desc">Acceso completo al sistema</div>
                </div>
              </div>
            </div>
          </div>

          {/* Permissions (encargado only) */}
          {newRole === "encargado" && (
            <div className="form-section">
              <h4 className="form-section-title">Permisos</h4>
              <p className="form-section-desc">Asigna los permisos específicos para el rol Encargado</p>
              <div className="perm-groups">
                {PERMISSION_GROUPS.map(group => (
                  <div key={group.category} className="perm-group">
                    <div className="perm-group-header">{group.category}</div>
                    <div className="perm-group-body">
                      {group.permissions.filter(p => p.key !== "manage_admins" || currentUser?.is_superadmin).map(p => (
                        <label key={p.key} className="perm-check">
                          <input
                            type="checkbox"
                            checked={newPermissions.includes(p.key)}
                            onChange={(e) => {
                              setNewPermissions(
                                e.target.checked
                                  ? [...newPermissions, p.key]
                                  : newPermissions.filter(k => k !== p.key)
                              );
                            }}
                          />
                          {p.label}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {newRole === "admin" && (
            <p style={{ color: "#64748b", fontSize: "0.85rem", fontStyle: "italic", margin: "12px 0" }}>
              Los administradores tienen acceso completo a todas las funciones del sistema.
            </p>
          )}

          {/* Buttons */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
            <button className="btn-secondary" onClick={() => { setShowCreate(false); setNewName(""); setNewEmail(""); setNewPermissions([]); setNewRole("encargado"); }}>
              Cancelar
            </button>
            <button
              className="btn-primary"
              onClick={() => {
                if (newRole === "admin") {
                  createAdminMutation.mutate();
                } else {
                  createMutation.mutate();
                }
              }}
              disabled={createMutation.isPending || createAdminMutation.isPending}
            >
              {createMutation.isPending || createAdminMutation.isPending ? "Creando..." : "Crear Usuario"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="loading-text">Cargando usuarios…</p>}

      {users && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {users.map(u => (
                editingId === u.id ? (
                  <Fragment key={u.id}>
                    <tr className="edit-row">
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
                    <tr>
                      <td colSpan={5} style={{ padding: "8px 12px", background: "#f9fafb" }}>
                        {editRole === "admin" ? (
                          <p style={{ color: "#64748b", fontSize: "0.85rem", fontStyle: "italic", margin: 0 }}>
                            Los administradores tienen acceso completo a todas las funciones del sistema.
                          </p>
                        ) : (
                          <div>
                            <label style={{ fontSize: "0.8rem", fontWeight: 600, display: "block", marginBottom: "4px" }}>Permisos</label>
                            <div className="perm-groups">
                              {PERMISSION_GROUPS.map(group => (
                                <div key={group.category} className="perm-group">
                                  <div className="perm-group-header">{group.category}</div>
                                  <div className="perm-group-body">
                                    {group.permissions.filter(p => p.key !== "manage_admins" || currentUser?.is_superadmin).map(p => (
                                      <label key={p.key} className="perm-check">
                                        <input
                                          type="checkbox"
                                          checked={editPermissions.includes(p.key)}
                                          onChange={(e) => {
                                            if (e.target.checked) {
                                              setEditPermissions([...editPermissions, p.key]);
                                            } else {
                                              setEditPermissions(editPermissions.filter(k => k !== p.key));
                                            }
                                          }}
                                        />
                                        {p.label}
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  </Fragment>
                ) : (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td>
                      {u.role}
                      {u.is_superadmin && (
                        <span style={{ marginLeft: "6px", padding: "1px 6px", fontSize: "0.7rem", borderRadius: "4px", background: "#e0e7ff", color: "#4338ca", fontWeight: 600, verticalAlign: "middle" }}>
                          Superadmin
                        </span>
                      )}
                    </td>
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
