import { Routes, Route, Navigate, Outlet, useNavigate } from "react-router-dom";
import { FormEvent, useState } from "react";
import { KeyRound, LogIn, ShieldCheck } from "lucide-react";
import { useAuth } from "./context/AuthContext";
import { changePassword } from "./api/auth";
import { Sidebar } from "./components/Sidebar";
import { AuthGuard } from "./components/AuthGuard";
import { DashboardView } from "./features/dashboard/DashboardView";
import { DoctorsPage } from "./features/doctors/DoctorsPage";
import { CalendarsPage } from "./features/calendars/CalendarsPage";
import { CalendarGrid } from "./features/calendars/CalendarGrid";
import { MissionView } from "./features/missions/MissionView";
import { ReportsView } from "./features/reports/ReportsView";
import { ImportView } from "./features/import/ImportView";
import { NotificationLog } from "./features/notifications/NotificationLog";
import { TelegramLinks } from "./features/telegram/TelegramLinks";
import { AuditLog } from "./features/audit/AuditLog";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AuthGuard />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="/calendars" element={<CalendarsPage />} />
          <Route path="/calendars/:calendarId" element={<CalendarGrid />} />
          <Route path="/doctors" element={<DoctorsPage />} />
          <Route path="/missions" element={<MissionView />} />
          <Route path="/reports" element={<ReportsView />} />
          <Route path="/import" element={<ImportView />} />
          <Route path="/notifications" element={<NotificationLog />} />
          <Route path="/telegram" element={<TelegramLinks />} />
          <Route path="/audit" element={<AuditLog />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function AppShell() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
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
      setMessage(err instanceof Error ? err.message : "Error al iniciar sesión.");
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
      setMessage(err instanceof Error ? err.message : "Error al cambiar contraseña.");
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
            <label>Contraseña<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" /></label>
            <button type="submit" disabled={isLoading}><LogIn size={18} />{isLoading ? "Entrando…" : "Entrar"}</button>
          </form>
        )}

        {step === "change-password" && (
          <form className="auth-form" onSubmit={handlePasswordChange}>
            <label>Nueva contraseña<input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} autoComplete="new-password" /></label>
            <button type="submit" disabled={isLoading}><KeyRound size={18} />{isLoading ? "Cambiando…" : "Cambiar contraseña"}</button>
          </form>
        )}
      </section>
    </main>
  );
}
