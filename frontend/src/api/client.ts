const configuredBase = import.meta.env.VITE_API_URL;
const BASE = configuredBase || `${window.location.protocol}//${window.location.hostname}:8999`;

let token: string | null = null;

export function setToken(t: string | null) { token = t; }
export function getToken() { return token; }

export async function apiFetch<T>(path: string, init: RequestInit = {}, responseType?: "blob"): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init.headers as Record<string, string> ?? {}),
  };
  // Don't set Content-Type for blob downloads
  if (responseType === "blob") {
    delete headers["Content-Type"];
  }
  const res = await fetch(`${BASE}/api${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    setToken(null);
    window.location.href = "/";
    throw new ApiError(401, "Sesión expirada. Redirigiendo al login...");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? "Error del servidor");
  }
  if (res.status === 204) return undefined as T;
  if (responseType === "blob") return res.blob() as Promise<T>;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  public detail: unknown;

  constructor(public status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message?: unknown }).message)
          : "Error del servidor";
    super(message);
    this.detail = detail;
  }
}
