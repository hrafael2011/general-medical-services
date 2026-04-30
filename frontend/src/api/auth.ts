import { apiFetch, setToken } from "./client";

export interface UserRead {
  id: string; name: string; email: string; role: string; active: boolean; must_change_password: boolean;
}
export interface LoginResponse { access_token: string; token_type: string; user: UserRead; }

export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<UserRead> {
  return apiFetch<UserRead>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}
