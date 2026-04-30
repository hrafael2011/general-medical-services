const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

let token: string | null = null;

export function setToken(t: string | null) { token = t; }
export function getToken() { return token; }

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init.headers as Record<string, string> ?? {}),
  };
  const res = await fetch(`${BASE}/api${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? "Error del servidor");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}
