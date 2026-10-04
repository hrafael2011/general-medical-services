import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Mail, ArrowLeft } from "lucide-react";
import { authApi } from "../../api/auth";
import { ApiError } from "../../api/client";

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
      if (err instanceof ApiError && err.status === 429) {
        setState("rate-limited");
      } else {
        setState("done");
      }
    }
  };

  if (state === "done" || state === "rate-limited") {
    const isRateLimited = state === "rate-limited";
    return (
      <main className="app-shell">
        <section className="auth-panel auth-panel--narrow auth-panel--centered">
          <div className="auth-header">
            <span
              className={`status-icon ${isRateLimited ? "status-icon--warning" : "status-icon--success"}`}
            >
              <ShieldCheck size={24} />
            </span>
            <h2>{isRateLimited ? "Demasiadas solicitudes" : "Solicitud enviada"}</h2>
            <p className="summary">
              {isRateLimited
                ? "Has excedido el límite de intentos. Espera una hora antes de volver a intentarlo, o contacta al administrador si necesitas acceso urgente."
                : "Si el email existe en nuestro sistema, recibirás un enlace para restablecer tu contraseña. Revisa tu bandeja de entrada y la carpeta de spam."}
            </p>
          </div>
          <button className="btn-primary" onClick={() => navigate("/login")}>
            <ArrowLeft size={14} /> Volver al inicio de sesión
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="auth-panel auth-panel--narrow">
        <div className="auth-header">
          <span className="status-icon">
            <ShieldCheck size={24} />
          </span>
          <h2>Recuperar contraseña</h2>
          <p className="summary">
            Ingresa tu correo electrónico y te enviaremos un enlace para restablecer tu contraseña.
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Correo electrónico
            <span className="input-icon-wrapper">
              <Mail size={16} className="input-icon" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@email.com"
                autoComplete="email"
                required
                autoFocus
              />
            </span>
          </label>

          <button
            type="submit"
            className="btn-primary btn-block"
            disabled={state === "submitting"}
          >
            {state === "submitting" ? "Enviando…" : "Enviar enlace de recuperación"}
          </button>

          <button type="button" className="btn-ghost btn-block" onClick={() => navigate("/login")}>
            <ArrowLeft size={14} /> Volver al inicio de sesión
          </button>
        </form>
      </section>
    </main>
  );
}
