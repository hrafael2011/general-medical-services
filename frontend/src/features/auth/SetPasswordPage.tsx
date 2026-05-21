import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { authApi } from "../../api/auth";
import { useToast } from "../../components/Toast";

type PageState = "loading" | "invalid" | "valid" | "submitting" | "done" | "error";

export function SetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const token = searchParams.get("token");

  const [state, setState] = useState<PageState>("loading");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("invalid");
      return;
    }
    authApi
      .validateSetPasswordToken(token)
      .then((res) => {
        if (res.valid && res.email && res.name) {
          setEmail(res.email);
          setName(res.name);
          setState("valid");
        } else {
          setState("invalid");
        }
      })
      .catch(() => setState("invalid"));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (password !== confirm) {
      setErrorMessage("Las contraseñas no coinciden.");
      return;
    }

    setState("submitting");
    try {
      await authApi.setPassword(token!, password);
      setState("done");
      addToast("success", "Contraseña creada exitosamente. Ahora puedes iniciar sesión.");
      setTimeout(() => navigate("/login", { replace: true }), 2000);
    } catch {
      setErrorMessage("Error al crear la contraseña. El enlace podría haber expirado.");
      setState("valid");
    }
  };

  if (state === "loading") {
    return (
      <div className="login-page">
        <div className="login-card">
          <p className="loading-text">Validando enlace…</p>
        </div>
      </div>
    );
  }

  if (state === "invalid") {
    return (
      <div className="login-page">
        <div className="login-card" style={{ textAlign: "center", padding: "40px" }}>
          <ShieldCheck size={40} style={{ color: "#dc2626", marginBottom: 16 }} />
          <h2 style={{ margin: "0 0 8px", color: "#1e293b" }}>Enlace inválido o expirado</h2>
          <p style={{ color: "#64748b", fontSize: 14, margin: "0 0 24px" }}>
            Este enlace ya fue utilizado o ha expirado (48 horas de validez).
          </p>
          <p style={{ color: "#64748b", fontSize: 13 }}>
            Contacta al administrador para que te envíe un nuevo enlace.
          </p>
          <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => navigate("/login")}>
            Ir al inicio de sesión
          </button>
        </div>
      </div>
    );
  }

  if (state === "done") {
    return (
      <div className="login-page">
        <div className="login-card" style={{ textAlign: "center", padding: "40px" }}>
          <ShieldCheck size={40} style={{ color: "#16a34a", marginBottom: 16 }} />
          <h2 style={{ margin: "0 0 8px", color: "#1e293b" }}>Contraseña creada</h2>
          <p style={{ color: "#64748b", fontSize: 14 }}>
            Redirigiendo al inicio de sesión…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <ShieldCheck size={36} style={{ color: "#2563eb", marginBottom: 8 }} />
          <h2 style={{ margin: 0, color: "#1e293b", fontSize: 20 }}>Crear contraseña</h2>
          <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
            Bienvenido{name ? `, ${name}` : ""}. Establece tu contraseña para continuar.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Correo electrónico</label>
            <input
              type="email"
              value={email}
              disabled
              className="form-input"
              style={{ background: "#f1f5f9", color: "#64748b", cursor: "not-allowed" }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Nueva contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="form-input"
              placeholder="••••••••••"
              minLength={10}
              required
            />
            <ul className="form-hint">
              <li>Mínimo 10 caracteres</li>
              <li>Al menos una mayúscula y una minúscula</li>
              <li>Al menos un número y un carácter especial</li>
            </ul>
          </div>

          <div className="form-group">
            <label className="form-label">Confirmar contraseña</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="form-input"
              placeholder="••••••••••"
              minLength={10}
              required
            />
          </div>

          {errorMessage && (
            <p style={{ color: "#dc2626", fontSize: 13, margin: "0 0 12px" }}>{errorMessage}</p>
          )}

          <button
            type="submit"
            className="btn-primary"
            style={{ width: "100%" }}
            disabled={state === "submitting"}
          >
            {state === "submitting" ? "Creando contraseña…" : "Crear contraseña y acceder"}
          </button>
        </form>

        <p style={{ fontSize: 11, color: "#94a3b8", textAlign: "center", marginTop: 16 }}>
          Este enlace expira en 48 horas y solo puede usarse una vez.
        </p>
      </div>
    </div>
  );
}
