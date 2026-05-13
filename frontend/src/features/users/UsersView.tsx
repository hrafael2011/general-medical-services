import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, UserPlus, KeyRound } from "lucide-react";
import { useToast } from "../../components/Toast";
import { adminApi, UserRead } from "../../api/admin";

export function UsersView() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => adminApi.listUsers("encargado"),
  });

  const createMutation = useMutation({
    mutationFn: () => adminApi.createEncargado(newName, newEmail),
    onSuccess: (res) => {
      // After creation, send invitation
      adminApi.inviteUser(res.user.id).catch(() => {});
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
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td>{u.role}</td>
                  <td>
                    {!u.active ? "No" : u.must_change_password ? "Pendiente" : "Activo"}
                  </td>
                  <td>
                    <button
                      className="btn-ghost"
                      style={{ padding: "3px 10px", fontSize: "0.8rem" }}
                      onClick={() => resetMutation.mutate(u.id)}
                      disabled={resetMutation.isPending}
                    >
                      <KeyRound size={13} /> {resetMutation.isPending ? "Enviando…" : "Resetear"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
