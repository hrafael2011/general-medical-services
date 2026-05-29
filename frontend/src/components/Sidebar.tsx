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

  const ROLE_LABELS: Record<string, { label: string; color: string }> = {
    admin: { label: "Administrador", color: "#3b82f6" },
    superadmin: { label: "Super Admin", color: "#8b5cf6" },
    encargado: { label: "Encargado", color: "#10b981" },
  };

  function avatarColor(name: string): string {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360;
    return `hsl(${h}, 55%, 45%)`;
  }

  function initials(name: string): string {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }

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
        <div className="sidebar-user-card">
          <div
            className="sidebar-user-avatar"
            style={{ backgroundColor: avatarColor(currentUser?.name ?? "") }}
          >
            {initials(currentUser?.name ?? "")}
          </div>
          <span className="sidebar-user-name">{currentUser?.name}</span>
          {currentUser?.role && ROLE_LABELS[currentUser.role] && (
            <span
              className="sidebar-user-role"
              style={{
                backgroundColor: ROLE_LABELS[currentUser.role].color + "1a",
                color: ROLE_LABELS[currentUser.role].color,
              }}
            >
              {ROLE_LABELS[currentUser.role].label}
            </span>
          )}
          <div className="sidebar-user-divider" />
          <button className="sidebar-logout-btn" onClick={logout}>
            <LogOut size={14} /> Cerrar sesión
          </button>
        </div>
      </div>
    </aside>
  );
}
