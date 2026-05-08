import { createContext, useContext, useState, ReactNode } from "react";
import { setToken } from "../api/client";
import { login as apiLogin, UserRead } from "../api/auth";

interface AuthContextValue {
  currentUser: UserRead | null;
  login: (email: string, password: string) => Promise<UserRead>;
  logout: () => void;
  setCurrentUser: (user: UserRead) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);

  async function login(email: string, password: string): Promise<UserRead> {
    const res = await apiLogin(email, password);
    setToken(res.access_token);
    setCurrentUser(res.user);
    return res.user;
  }

  function logout() {
    setToken(null);
    setCurrentUser(null);
  }

  return (
    <AuthContext.Provider value={{ currentUser, login, logout, setCurrentUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
