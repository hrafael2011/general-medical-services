import { NavLink } from "react-router-dom";
import {
  CalendarDays, Stethoscope, Target, BarChart2, Upload,
  Bell, MessageCircle, ClipboardList, ShieldCheck, LogOut,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV_GROUPS = [
  {
    label: "OPERACIONES",
    items: [
      { to: "/calendars", icon: CalendarDays, label: "Calendarios" },
      { to: "/doctors",   icon: Stethoscope,  label: "Médicos" },
      { to: "/missions",  icon: Target,        label: "Misiones" },
    ],
  },
  {
    label: "DATOS",
    items: [
      { to: "/reports", icon: BarChart2, label: "Reportes" },
      { to: "/import",  icon: Upload,    label: "Importar" },
    ],
  },
  {
    label: "SISTEMA",
    items: [
      { to: "/notifications", icon: Bell,          label: "Notificaciones" },
      { to: "/telegram",      icon: MessageCircle, label: "Telegram" },
      { to: "/audit",         icon: ClipboardList, label: "Auditoría" },
    ],
  },
];

export function Sidebar() {
  const { currentUser, logout } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <ShieldCheck size={20} className="sidebar-logo-icon" />
        <span className="sidebar-title">Sistema de Turnos</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_GROUPS.map(group => (
          <div key={group.label} className="sidebar-group">
            <span className="sidebar-group-label">{group.label}</span>
            {group.items.map(({ to, icon: Icon, label }) => (
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
        ))}
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
