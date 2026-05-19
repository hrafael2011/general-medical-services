import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function AuthGuard() {
  const { currentUser, isAuthLoading } = useAuth();
  if (isAuthLoading) return <p className="loading-text">Restaurando sesión…</p>;
  if (!currentUser) return <Navigate to="/login" replace />;
  return <Outlet />;
}
