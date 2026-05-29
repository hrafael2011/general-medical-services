import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getToken, setToken } from "../api/client";
import { authApi, login as apiLogin, UserRead } from "../api/auth";

interface AuthContextValue {
  currentUser: UserRead | null;
  isAuthLoading: boolean;
  login: (email: string, password: string) => Promise<UserRead>;
  logout: () => void;
  setCurrentUser: (user: UserRead) => void;
  justLoggedIn: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(() => Boolean(getToken()));
  const [justLoggedIn, setJustLoggedIn] = useState(false);

  useEffect(() => {
    const storedToken = getToken();
    if (!storedToken) {
      setIsAuthLoading(false);
      return;
    }

    let cancelled = false;
    authApi.me()
      .then((user) => {
        if (!cancelled) setCurrentUser(user);
      })
      .catch(() => {
        if (!cancelled) {
          setToken(null);
          setCurrentUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsAuthLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function login(email: string, password: string): Promise<UserRead> {
    const res = await apiLogin(email, password);
    setToken(res.access_token);
    setCurrentUser(res.user);
    setJustLoggedIn(true);
    return res.user;
  }

  function logout() {
    setToken(null);
    setCurrentUser(null);
    setIsAuthLoading(false);
  }

  return (
    <AuthContext.Provider value={{ currentUser, isAuthLoading, justLoggedIn, login, logout, setCurrentUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
