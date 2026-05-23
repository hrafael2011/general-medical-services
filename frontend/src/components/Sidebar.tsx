import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard, CalendarDays, Stethoscope, Target,
  BarChart2, Bell, MessageCircle, CheckCircle,
  BookOpen, ClipboardList, ShieldCheck, LogOut, UserPlus, Trash2,
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

  const alertCounts = alertSummary?.by_section ?? {};

  const hasPermission = (perm: string) => {
    if (currentUser?.role === "admin") return true;
    return (currentUser?.permissions ?? []).includes(perm);
  };

  const hasAnySecurityPerm = hasPermission("manage_users") || hasPermission("manage_catalogs") || hasPermission("view_audit") || hasPermission("manage_trash");

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

        {hasPermission("export_reports") && (
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

        {hasAnySecurityPerm && (
          <div className="sidebar-group">
            <span className="sidebar-group-label">SEGURIDAD</span>
            {hasPermission("view_audit") && (
              <NavLink
                to="/audit"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <ClipboardList size={16} />
                Auditoría
              </NavLink>
            )}
            {hasPermission("manage_catalogs") && (
              <NavLink
                to="/catalogs"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <BookOpen size={16} />
                Catálogos
              </NavLink>
            )}
            {hasPermission("manage_users") && (
              <NavLink
                to="/users"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <UserPlus size={16} />
                Usuarios
              </NavLink>
            )}
            {hasPermission("manage_trash") && (
              <NavLink
                to="/trash"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <Trash2 size={16} />
                Papelera
              </NavLink>
            )}
          </div>
        )}

        {(featureFlags?.notifications || featureFlags?.telegram) && (
          <div className="sidebar-group">
            <span className="sidebar-group-label">NOTIFICACIONES</span>
            {featureFlags?.notifications && hasPermission("view_notifications") && (
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
            {featureFlags?.confirmations && (
              <NavLink
                to="/confirmations"
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                <CheckCircle size={16} />
                <span className="sidebar-link-label">Confirmaciones</span>
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
