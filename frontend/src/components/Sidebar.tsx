import { NavLink } from "react-router-dom";
import {
  CalendarDays, Stethoscope, Target,
  BarChart2, Bell, MessageCircle,
  ClipboardList, ShieldCheck, LogOut, UserPlus,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const SHARED_ITEMS = [
  { to: "/calendars", icon: CalendarDays, label: "Calendarios" },
  { to: "/doctors",   icon: Stethoscope,  label: "Médicos" },
  { to: "/missions",  icon: Target,        label: "Misiones" },
];

const SYSTEM_ITEMS = [
  { to: "/notifications", icon: Bell,          label: "Notificaciones" },
  { to: "/telegram",      icon: MessageCircle, label: "Telegram" },
];

export function Sidebar() {
  const { currentUser, logout } = useAuth();

  const isEncargadoPlus = currentUser && (currentUser.role === "encargado" || currentUser.role === "admin");
  const isAdmin = currentUser && currentUser.role === "admin";

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <ShieldCheck size={20} className="sidebar-logo-icon" />
        <span className="sidebar-title">Sistema de Turnos</span>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-group">
          <span className="sidebar-group-label">OPERACIONES</span>
          {SHARED_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </div>

        {isEncargadoPlus && (
          <div className="sidebar-group">
            <span className="sidebar-group-label">ADMINISTRACIÓN</span>
            <NavLink
              to="/reports"
              className={({ isActive }) =>
                isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
              }
            >
              <BarChart2 size={16} />
              Reportes
            </NavLink>
          </div>
        )}

        {isAdmin && (
          <div className="sidebar-group">
            <span className="sidebar-group-label">SEGURIDAD</span>
            <NavLink
              to="/audit"
              className={({ isActive }) =>
                isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
              }
            >
              <ClipboardList size={16} />
              Auditoría
            </NavLink>
            <NavLink
              to="/users"
              className={({ isActive }) =>
                isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
              }
            >
              <UserPlus size={16} />
              Usuarios
            </NavLink>
          </div>
        )}

        <div className="sidebar-group">
          <span className="sidebar-group-label">NOTIFICACIONES</span>
          {SYSTEM_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="sidebar-footer">
        <span className="sidebar-user">{currentUser?.name}</span>
        <button className="btn-ghost" onClick={logout}>
          <LogOut size={14} /> Salir
        </button>
      </div>
    </aside>
  );
}
