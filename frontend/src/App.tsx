import { BarChart2, Bell, CalendarDays, ClipboardList, KeyRound, LogIn, MessageCircle, ShieldCheck, Stethoscope, LogOut, Target, Upload } from "lucide-react";
import { FormEvent, useState } from "react";
import { login, changePassword, UserRead } from "./api/auth";
import { DoctorList } from "./features/doctors/DoctorList";
import { AuditLog } from "./features/audit/AuditLog";
import { DoctorForm } from "./features/doctors/DoctorForm";
import { CalendarList } from "./features/calendars/CalendarList";
import { CalendarGrid } from "./features/calendars/CalendarGrid";
import { MissionView } from "./features/missions/MissionView";
import { NotificationLog } from "./features/notifications/NotificationLog";
import { TelegramLinks } from "./features/telegram/TelegramLinks";
import { ImportView } from "./features/import/ImportView";
import { ReportsView } from "./features/reports/ReportsView";
import { DoctorRead } from "./api/doctors";
import { setToken } from "./api/client";
import "./styles.css";

type View = "login" | "change-password" | "dashboard" | "doctors" | "audit" | "calendars" | "missions" | "notifications" | "telegram" | "import" | "reports";

export function App() {
  const [view, setView] = useState<View>("login");
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [email, setEmail] = useState("admin@turnos.com");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("Ingresa con tu usuario asignado.");
  const [isLoading, setIsLoading] = useState(false);
  const [editingDoctor, setEditingDoctor] = useState<DoctorRead | undefined>(undefined);
  const [showDoctorForm, setShowDoctorForm] = useState(false);
  const [selectedCalendarId, setSelectedCalendarId] = useState<string | null>(null);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    try {
      const res = await login(email, password);
      setCurrentUser(res.user);
      if (res.user.must_change_password) {
        setMessage("Por seguridad debes cambiar la contrasena temporal.");
        setView("change-password");
      } else {
        setMessage("Acceso habilitado.");
        setView("dashboard");
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Error al iniciar sesion.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword.length < 10) {
      setMessage("La nueva contrasena debe tener al menos 10 caracteres.");
      return;
    }
    setIsLoading(true);
    try {
      const user = await changePassword(password, newPassword);
      setCurrentUser(user);
      setMessage("Acceso habilitado.");
      setView("dashboard");
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Error al cambiar contrasena.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleLogout() {
    setToken(null);
    setCurrentUser(null);
    setEmail("admin@turnos.com");
    setPassword("");
    setNewPassword("");
    setMessage("Ingresa con tu usuario asignado.");
    setView("login");
  }

  const isOperational = view === "dashboard" || view === "doctors" || view === "audit" || view === "calendars" || view === "missions" || view === "notifications" || view === "telegram" || view === "import" || view === "reports";

  return (
    <main className={isOperational ? "app-shell app-wide" : "app-shell"}>
      <section className={isOperational ? "op-panel" : "auth-panel"} aria-labelledby="app-title">
        <header className="auth-header">
          <div className="status-icon">
            <ShieldCheck size={28} />
          </div>
          <div style={{ flex: 1 }}>
            <p className="eyebrow">Panel operativo</p>
            <h1 id="app-title">Sistema de turnos medicos</h1>
            {!isOperational && <p className="summary">{message}</p>}
          </div>
          {isOperational && (
            <div className="top-nav">
              <span className="user-name">{currentUser?.name}</span>
              <button className="btn-ghost" onClick={handleLogout}>
                <LogOut size={16} /> Salir
              </button>
            </div>
          )}
        </header>

        {isOperational && (
          <nav className="op-nav">
            <button
              className={view === "dashboard" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("dashboard")}
            >
              <ShieldCheck size={16} /> Panel
            </button>
            <button
              className={view === "doctors" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("doctors")}
            >
              <Stethoscope size={16} /> Medicos
            </button>
            <button
              className={view === "audit" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("audit")}
            >
              <ClipboardList size={16} /> Auditoría
            </button>
            <button
              className={view === "calendars" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => { setSelectedCalendarId(null); setView("calendars"); }}
            >
              <CalendarDays size={16} /> Calendarios
            </button>
            <button
              className={view === "missions" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("missions")}
            >
              <Target size={16} /> Misiones
            </button>
            <button
              className={view === "notifications" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("notifications")}
            >
              <Bell size={16} /> Notificaciones
            </button>
            <button
              className={view === "telegram" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("telegram")}
            >
              <MessageCircle size={16} /> Telegram
            </button>
            <button
              className={view === "import" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("import")}
            >
              <Upload size={16} /> Importar
            </button>
            <button
              className={view === "reports" ? "nav-btn nav-active" : "nav-btn"}
              onClick={() => setView("reports")}
            >
              <BarChart2 size={16} /> Reportes
            </button>
          </nav>
        )}

        {view === "login" && (
          <form className="auth-form" onSubmit={handleLogin}>
            <label>
              Correo
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" />
            </label>
            <label>
              Contrasena
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
            </label>
            <button type="submit" disabled={isLoading}>
              <LogIn size={18} /> {isLoading ? "Entrando…" : "Entrar"}
            </button>
          </form>
        )}

        {view === "change-password" && (
          <form className="auth-form" onSubmit={handlePasswordChange}>
            <label>
              Nueva contrasena
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} autoComplete="new-password" />
            </label>
            <button type="submit" disabled={isLoading}>
              <KeyRound size={18} /> {isLoading ? "Cambiando…" : "Cambiar contrasena"}
            </button>
          </form>
        )}

        {view === "dashboard" && (
          <div className="dashboard-preview">
            <div className="ready-state">
              <ShieldCheck size={22} />
              <span>Usuario listo para operar el panel.</span>
            </div>
            <div className="catalog-grid">
              {[
                { title: "Areas MVP", value: "Emergencia, Pista, Disponible", detail: "Un medico por area cada dia." },
                { title: "Causas de bloqueo", value: "8 iniciales", detail: "Incluye licencia, embarazo, no realiza servicio y otro." },
                { title: "Configuracion", value: "Dia 27", detail: "Generacion mensual configurable." },
              ].map(card => (
                <article className="catalog-card" key={card.title}>
                  <h2>{card.title}</h2>
                  <strong>{card.value}</strong>
                  <p>{card.detail}</p>
                </article>
              ))}
            </div>
          </div>
        )}

        {view === "doctors" && (
          <DoctorList
            onAdd={() => { setEditingDoctor(undefined); setShowDoctorForm(true); }}
            onEdit={doc => { setEditingDoctor(doc); setShowDoctorForm(true); }}
          />
        )}

        {view === "audit" && <AuditLog />}

        {view === "calendars" && !selectedCalendarId && (
          <CalendarList onSelect={id => setSelectedCalendarId(id)} />
        )}

        {view === "calendars" && selectedCalendarId && (
          <CalendarGrid
            calendarId={selectedCalendarId}
            onBack={() => setSelectedCalendarId(null)}
          />
        )}

        {view === "missions" && <MissionView />}

        {view === "notifications" && <NotificationLog />}

        {view === "telegram" && <TelegramLinks />}

        {view === "import" && <ImportView />}

        {view === "reports" && <ReportsView />}

        {showDoctorForm && (
          <DoctorForm
            doctor={editingDoctor}
            onClose={() => { setShowDoctorForm(false); setEditingDoctor(undefined); }}
          />
        )}
      </section>
    </main>
  );
}
