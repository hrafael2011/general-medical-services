import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard, CalendarDays, Stethoscope, Target,
  BarChart2, Bell, MessageCircle,
  ClipboardList, ShieldCheck, LogOut, UserPlus,
} from "lucide-react";
import { actionAlertsApi } from "../api/actionAlerts";
import { fetchFeatureFlags } from "../api/featureFlags";
import { useAuth } from "../context/AuthContext";

const SHARED_ITEMS = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/calendars", icon: CalendarDays,     label: "Calendarios" },
  { to: "/doctors",   icon: Stethoscope,      label: "Médicos" },
  { to: "/missions",  icon: Target,            label: "Misiones" },
];


export function Sidebar() {
  const { currentUser, logout } = useAuth();
  const { data: alertSummary } = useQuery({
    queryKey: ["action-alerts-summary"],
    queryFn: actionAlertsApi.summary,
    staleTime: 60 * 1000,
  });
  const { data: featureFlags } = useQuery({
    queryKey: ["feature-flags"],
    queryFn: fetchFeatureFlags,
    staleTime: 5 * 60 * 1000,
  });

  const isEncargadoPlus = currentUser && (currentUser.role === "encargado" || currentUser.role === "admin");
  const isAdmin = currentUser && currentUser.role === "admin";
  const alertCounts = alertSummary?.by_section ?? {};

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
              <span className="sidebar-link-label">{label}</span>
              {to === "/missions" && (alertCounts.missions ?? 0) > 0 && (
                <span className="sidebar-badge" aria-label={`${alertCounts.missions} alertas en misiones`}>
                  {alertCounts.missions}
                </span>
              )}
              {to === "/calendars" && (alertCounts.calendar ?? 0) > 0 && (
                <span className="sidebar-badge" aria-label={`${alertCounts.calendar} alertas en calendarios`}>
                  {alertCounts.calendar}
                </span>
              )}
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

        {(featureFlags?.notifications || featureFlags?.telegram) && (
          <div className="sidebar-group">
            <span className="sidebar-group-label">NOTIFICACIONES</span>
            {featureFlags?.notifications && (
              <NavLink
                to="/notifications"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <Bell size={16} />
                <span className="sidebar-link-label">Notificaciones</span>
                {(alertCounts.notifications ?? 0) > 0 && (
                  <span className="sidebar-badge" aria-label={`${alertCounts.notifications} alertas en notificaciones`}>
                    {alertCounts.notifications}
                  </span>
                )}
              </NavLink>
            )}
            {featureFlags?.telegram && (
              <NavLink
                to="/telegram"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <MessageCircle size={16} />
                <span className="sidebar-link-label">Telegram</span>
              </NavLink>
            )}
          </div>
        )}
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
