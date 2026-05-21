import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Mail, ArrowLeft } from "lucide-react";
import { authApi } from "../../api/auth";

type PageState = "idle" | "submitting" | "done" | "rate-limited";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<PageState>("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setState("submitting");
    try {
      await authApi.forgotPassword(email.trim());
      setState("done");
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes("429")) {
        setState("rate-limited");
      } else {
        setState("done");
      }
    }
  };

  if (state === "done") {
    return (
      <div className="login-page">
        <div className="login-card" style={{ textAlign: "center", padding: "40px" }}>
          <ShieldCheck size={40} style={{ color: "#16a34a", marginBottom: 16 }} />
          <h2 style={{ margin: "0 0 8px", color: "#1e293b" }}>Solicitud enviada</h2>
          <p style={{ color: "#64748b", fontSize: 14, margin: "0 0 24px", lineHeight: 1.6 }}>
            Si el email existe en nuestro sistema, recibiras un enlace para restablecer tu
            contrasena. Revisa tu bandeja de entrada y la carpeta de spam.
          </p>
          <button className="btn-primary" onClick={() => navigate("/login")}>
            <ArrowLeft size={14} /> Volver al inicio de sesion
          </button>
        </div>
      </div>
    );
  }

  if (state === "rate-limited") {
    return (
      <div className="login-page">
        <div className="login-card" style={{ textAlign: "center", padding: "40px" }}>
          <ShieldCheck size={40} style={{ color: "#f59e0b", marginBottom: 16 }} />
          <h2 style={{ margin: "0 0 8px", color: "#1e293b" }}>Demasiadas solicitudes</h2>
          <p style={{ color: "#64748b", fontSize: 14, margin: "0 0 24px", lineHeight: 1.6 }}>
            Has excedido el limite de intentos. Espera una hora antes de volver a intentarlo,
            o contacta al administrador si necesitas acceso urgente.
          </p>
          <button className="btn-primary" onClick={() => navigate("/login")}>
            <ArrowLeft size={14} /> Volver al inicio de sesion
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <ShieldCheck size={36} style={{ color: "#2563eb", marginBottom: 8 }} />
          <h2 style={{ margin: 0, color: "#1e293b", fontSize: 20 }}>Recuperar contrasena</h2>
          <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
            Ingresa tu correo electronico y te enviaremos un enlace para restablecer tu contrasena.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Correo electronico</label>
            <div style={{ position: "relative" }}>
              <Mail
                size={16}
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#94a3b8",
                }}
              />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="form-input"
                placeholder="tu@email.com"
                style={{ paddingLeft: 36 }}
                required
                autoFocus
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary"
            style={{ width: "100%" }}
            disabled={state === "submitting"}
          >
            {state === "submitting" ? "Enviando..." : "Enviar enlace de recuperacion"}
          </button>
        </form>

        <button
          className="btn-ghost"
          style={{ width: "100%", marginTop: 12, justifyContent: "center", display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: "#64748b" }}
          onClick={() => navigate("/login")}
        >
          <ArrowLeft size={14} /> Volver al inicio de sesion
        </button>
      </div>
    </div>
  );
}
