import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { UserCircle, KeyRound, Check } from "lucide-react";
import { changePassword, updateProfile, PASSWORD_MIN_LENGTH } from "../../api/auth";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../components/Toast";
import { ApiError } from "../../api/client";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrador",
  encargado: "Encargado",
};

/** The user's own account.
 *
 *  Only the name is editable: it is what the weekly list PDF prints as the left
 *  signature. The email is the login identity and the password recovery destination,
 *  so it is shown read-only; the role and permissions are never self-service.
 */
export function ProfilePage() {
  const { currentUser, setCurrentUser } = useAuth();
  const { addToast } = useToast();
  const [name, setName] = useState(currentUser?.name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const nameMutation = useMutation({
    mutationFn: (value: string) => updateProfile(value),
    onSuccess: (user) => {
      setCurrentUser(user);
      setName(user.name);
      addToast("success", "Nombre actualizado.");
    },
    onError: (err: Error) => addToast("error", err.message || "No se pudo guardar el nombre."),
  });

  const passwordMutation = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordError(null);
      addToast("success", "Contraseña actualizada.");
    },
    onError: (err: unknown) => {
      // The backend answers with the exact cause; show it instead of a guess.
      const message =
        err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña.";
      setPasswordError(message);
    },
  });

  function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError("Las contraseñas no coinciden.");
      return;
    }
    setPasswordError(null);
    passwordMutation.mutate();
  }

  const sectionStyle = {
    background: "#f9fafb",
    padding: "16px",
    borderRadius: "8px",
    marginBottom: "20px",
  } as const;
  const fieldStyle = { display: "flex", flexDirection: "column", gap: "4px" } as const;
  const inputStyle = { width: "100%", boxSizing: "border-box" } as const;

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <UserCircle size={20} />
          <h2>Mi perfil</h2>
        </div>
      </div>

      <div style={{ maxWidth: 560 }}>
        <div style={sectionStyle}>
          <h4 style={{ margin: "0 0 4px", fontSize: "0.9rem" }}>Mis datos</h4>
          <p style={{ color: "#64748b", fontSize: "0.82rem", margin: "0 0 12px" }}>
            El <strong>nombre</strong> es el que aparece en la firma de la lista semanal.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <label style={fieldStyle}>
              Nombre
              <input
                type="text"
                style={inputStyle}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label style={fieldStyle}>
              Correo
              <input type="text" style={inputStyle} value={currentUser?.email ?? ""} readOnly disabled />
            </label>
            <label style={fieldStyle}>
              Rol
              <input
                type="text"
                style={inputStyle}
                value={ROLE_LABELS[currentUser?.role ?? ""] ?? currentUser?.role ?? ""}
                readOnly
                disabled
              />
            </label>
          </div>
          <div style={{ marginTop: "12px" }}>
            <button
              className="btn-primary"
              onClick={() => nameMutation.mutate(name)}
              disabled={nameMutation.isPending || !name.trim() || name === currentUser?.name}
            >
              <Check size={14} /> {nameMutation.isPending ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>

        <form style={sectionStyle} onSubmit={handlePasswordSubmit}>
          <h4 style={{ margin: "0 0 4px", fontSize: "0.9rem" }}>
            <KeyRound size={14} /> Cambiar contraseña
          </h4>
          <p style={{ color: "#64748b", fontSize: "0.82rem", margin: "0 0 12px" }}>
            Puedes cambiarla cuando quieras, no solo al entrar por primera vez.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <label style={fieldStyle}>
              Contraseña actual
              <input
                type="password"
                autoComplete="current-password"
                style={inputStyle}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </label>
            <label style={fieldStyle}>
              Contraseña nueva
              <input
                type="password"
                autoComplete="new-password"
                minLength={PASSWORD_MIN_LENGTH}
                style={inputStyle}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </label>
            <label style={fieldStyle}>
              Confirmar contraseña nueva
              <input
                type="password"
                autoComplete="new-password"
                minLength={PASSWORD_MIN_LENGTH}
                style={inputStyle}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </label>
          </div>

          <ul style={{ color: "#64748b", fontSize: "0.78rem", margin: "10px 0 0 0", paddingLeft: "18px" }}>
            <li>Mínimo {PASSWORD_MIN_LENGTH} caracteres</li>
            <li>Al menos una mayúscula y una minúscula</li>
            <li>Al menos un número y un carácter especial</li>
            <li>No puede repetir una de tus últimas 5 contraseñas</li>
          </ul>

          {passwordError && (
            <p style={{ color: "#b91c1c", fontSize: "0.82rem", margin: "10px 0 0" }} role="alert">
              {passwordError}
            </p>
          )}

          <div style={{ marginTop: "12px" }}>
            <button
              className="btn-primary"
              type="submit"
              disabled={passwordMutation.isPending || !currentPassword || !newPassword}
            >
              {passwordMutation.isPending ? "Cambiando…" : "Cambiar contraseña"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
