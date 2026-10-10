import { useState, useEffect, type ReactNode } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { authApi, PASSWORD_MIN_LENGTH } from "../../api/auth";
import { useToast } from "../../components/Toast";

type PageState = "loading" | "invalid" | "valid" | "submitting" | "done";

/** Shared shell for the states that only report an outcome, with no form. */
function StatusPanel({
  tone,
  title,
  children,
  action,
}: {
  tone: "success" | "danger";
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <main className="app-shell">
      <section className="auth-panel auth-panel--narrow auth-panel--centered">
        <div className="auth-header">
          <span className={`status-icon status-icon--${tone}`}>
            <ShieldCheck size={24} />
          </span>
          <h2>{title}</h2>
          {children}
        </div>
        {action}
      </section>
    </main>
  );
}

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
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al crear la contraseña. El enlace podría haber expirado.";
      setErrorMessage(message);
      setState("valid");
    }
  };

  if (state === "loading") {
    return (
      <main className="app-shell">
        <section className="auth-panel auth-panel--narrow auth-panel--centered">
          <p className="loading-text">Validando enlace…</p>
        </section>
      </main>
    );
  }

  if (state === "invalid") {
    return (
      <StatusPanel
        tone="danger"
        title="Enlace inválido o expirado"
        action={
          <button className="btn-primary" onClick={() => navigate("/login")}>
            Ir al inicio de sesión
          </button>
        }
      >
        <p className="summary">Este enlace ya fue utilizado o ha expirado (48 horas de validez).</p>
        <p className="summary">Contacta al administrador para que te envíe un nuevo enlace.</p>
      </StatusPanel>
    );
  }

  if (state === "done") {
    return (
      <StatusPanel tone="success" title="Contraseña creada">
        <p className="summary">Redirigiendo al inicio de sesión…</p>
      </StatusPanel>
    );
  }

  return (
    <main className="app-shell">
      <section className="auth-panel auth-panel--narrow">
        <div className="auth-header">
          <span className="status-icon">
            <ShieldCheck size={24} />
          </span>
          <h2>Crear contraseña</h2>
          <p className="summary">
            Bienvenido{name ? `, ${name}` : ""}. Establece tu contraseña para continuar.
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Correo electrónico
            <input type="email" value={email} disabled autoComplete="username" />
          </label>

          <label>
            Nueva contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
              autoComplete="new-password"
              minLength={PASSWORD_MIN_LENGTH}
              required
            />
            <ul className="auth-hint">
              <li>Mínimo {PASSWORD_MIN_LENGTH} caracteres</li>
              <li>Al menos una mayúscula y una minúscula</li>
              <li>Al menos un número y un carácter especial</li>
            </ul>
          </label>

          <label>
            Confirmar contraseña
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••••"
              autoComplete="new-password"
              minLength={PASSWORD_MIN_LENGTH}
              required
            />
          </label>

          {errorMessage && <p className="form-error">{errorMessage}</p>}

          <button
            type="submit"
            className="btn-primary btn-block"
            disabled={state === "submitting"}
          >
            {state === "submitting" ? "Creando contraseña…" : "Crear contraseña y acceder"}
          </button>
        </form>

        <p className="auth-footnote">
          Este enlace expira en 48 horas y solo puede usarse una vez.
        </p>
      </section>
    </main>
  );
}
