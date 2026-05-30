import { Routes, Route, Navigate, Outlet, useNavigate } from "react-router-dom";
import { FormEvent, useState, useEffect } from "react";
import { Eye, EyeOff, KeyRound, LogIn, ShieldCheck } from "lucide-react";
import { useAuth } from "./context/AuthContext";
import { changePassword } from "./api/auth";
import { ApiError } from "./api/client";
import { Sidebar } from "./components/Sidebar";
import { AlertBell } from "./components/AlertBell";
import { WelcomeToast } from "./components/WelcomeToast";
import { AuthGuard } from "./components/AuthGuard";
import { DashboardView } from "./features/dashboard/DashboardView";
import { DoctorsPage } from "./features/doctors/DoctorsPage";
import { CalendarsPage } from "./features/calendars/CalendarsPage";
import { CalendarGrid } from "./features/calendars/CalendarGrid";
import { MissionView } from "./features/missions/MissionView";
import { ReportsView } from "./features/reports/ReportsView";
import { NotificationLog } from "./features/notifications/NotificationLog";
import { TelegramLinks } from "./features/telegram/TelegramLinks";
import { AuditLog } from "./features/audit/AuditLog";
import { UsersView } from "./features/users/UsersView";
import { CatalogsPage } from "./features/catalogs/CatalogsPage";
import { TrashPage } from "./features/trash/TrashPage";
import { SetPasswordPage } from "./features/auth/SetPasswordPage";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { PublicConfirmationPage } from "./features/confirmations/PublicConfirmationPage";
import { ConfirmationManagementPanel } from "./features/confirmations/ConfirmationManagementPanel";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/set-password" element={<SetPasswordPage />} />
      <Route path="/confirmacion-medica" element={<PublicConfirmationPage />} />
      <Route element={<AuthGuard />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="/calendars" element={<CalendarsPage />} />
          <Route path="/calendars/:calendarId" element={<CalendarGrid />} />
          <Route path="/doctors" element={<DoctorsPage />} />
          <Route path="/missions" element={<MissionView />} />
          <Route path="/notifications" element={<NotificationLog />} />
          <Route path="/confirmations" element={<ConfirmationManagementPanel />} />
          <Route path="/telegram" element={<TelegramLinks />} />
          <Route path="/reports" element={<ReportsView />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/users" element={<UsersView />} />
          <Route path="/catalogs" element={<CatalogsPage />} />
          <Route path="/trash" element={<TrashPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function AppShell() {
  const { justLoggedIn, currentUser } = useAuth();
  const [showToast, setShowToast] = useState(false);

  useEffect(() => {
    if (justLoggedIn && currentUser) {
      setShowToast(true);
    }
  }, [justLoggedIn, currentUser]);

  function handleToastDone() {
    setShowToast(false);
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="top-alert-bar">
          <AlertBell />
        </div>
        <Outlet />
      </main>
      {showToast && (
        <WelcomeToast userName={currentUser?.name ?? ""} onDone={handleToastDone} />
      )}
    </div>
  );
}

function LoginPage() {
  const { login, currentUser, setCurrentUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<"login" | "change-password">("login");
  const [email, setEmail] = useState("admin@turnos.com");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("Ingresa con tu usuario asignado.");
  const [isLoading, setIsLoading] = useState(false);

  if (currentUser && !currentUser.must_change_password && step === "login") {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    try {
      const user = await login(email, password);
      if (user.must_change_password) {
        setMessage("Por seguridad debes cambiar la contraseña temporal.");
        setStep("change-password");
      } else {
        navigate("/dashboard", { replace: true });
      }
    } catch (err: unknown) {
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        setMessage("Error de conexión. Verifica tu conexión a internet.");
      } else if (err instanceof ApiError && err.status === 401) {
        setMessage("Credenciales incorrectas. Verifica tu email y contraseña.");
      } else if (err instanceof ApiError && err.status === 423) {
        setMessage(err.message || "Cuenta bloqueada temporalmente.");
      } else if (err instanceof ApiError && err.status === 403) {
        setMessage(err.message || "Tu cuenta está desactivada.");
      } else {
        setMessage(err instanceof Error ? err.message : "Error al iniciar sesión.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function handlePasswordChange(e: FormEvent) {
    e.preventDefault();
    if (newPassword.length < 10) {
      setMessage("La nueva contraseña debe tener al menos 10 caracteres.");
      return;
    }
    setIsLoading(true);
    try {
      const user = await changePassword(password, newPassword);
      setCurrentUser(user);
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        setMessage("Error de conexión. Verifica tu conexión a internet.");
      } else {
        setMessage(err instanceof Error ? err.message : "Error al cambiar contraseña.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="auth-panel" aria-labelledby="app-title">
        <header className="auth-header">
          <div className="status-icon"><ShieldCheck size={28} /></div>
          <div>
            <p className="eyebrow">Panel operativo</p>
            <h1 id="app-title">Sistema de turnos médicos</h1>
            <p className="summary">{message}</p>
          </div>
        </header>

        {step === "login" && (
          <form className="auth-form" onSubmit={handleLogin}>
            <label>Correo<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" /></label>
            <label>Contraseña<span className="password-wrapper"><input type={showPassword ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" /><button type="button" className="password-toggle" onClick={() => setShowPassword(p => !p)} tabIndex={-1} aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></span></label>
            <button type="submit" disabled={isLoading}><LogIn size={18} />{isLoading ? "Entrando…" : "Entrar"}</button>
            <p style={{ textAlign: "center", marginTop: 16, fontSize: 13 }}>
              <button
                type="button"
                className="btn-ghost"
                style={{ color: "#64748b", fontSize: 13, textDecoration: "underline", background: "none", border: "none", cursor: "pointer", padding: 0 }}
                onClick={() => navigate("/forgot-password")}
              >
                ¿Olvidaste tu contraseña?
              </button>
            </p>
          </form>
        )}

        {step === "change-password" && (
          <form className="auth-form" onSubmit={handlePasswordChange}>
            <label>Nueva contraseña<span className="password-wrapper"><input type={showPassword ? "text" : "password"} value={newPassword} onChange={e => setNewPassword(e.target.value)} autoComplete="new-password" /><button type="button" className="password-toggle" onClick={() => setShowPassword(p => !p)} tabIndex={-1} aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></span></label>
            <button type="submit" disabled={isLoading}><KeyRound size={18} />{isLoading ? "Cambiando…" : "Cambiar contraseña"}</button>
          </form>
        )}
      </section>
    </main>
  );
}
