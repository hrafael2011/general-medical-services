import { apiFetch, setToken } from "./client";

export interface UserRead {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
  must_change_password: boolean;
  is_superadmin: boolean;
  permissions: string[];
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

/** Update your own account. Only the display name is accepted: the email, role and
 *  permissions are never self-service. */
export async function updateProfile(name: string): Promise<UserRead> {
  return apiFetch<UserRead>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

/** Minimum the backend enforces. Kept in sync by hand — it is the only copy here. */
export const PASSWORD_MIN_LENGTH = 8;

export interface SetPasswordValidateResponse {
  valid: boolean;
  email?: string;
  name?: string;
  expires_at?: string;
}

export const authApi = {
  me() {
    return apiFetch<UserRead>("/auth/me");
  },

  validateSetPasswordToken(token: string) {
    return apiFetch<SetPasswordValidateResponse>(
      `/auth/set-password?token=${encodeURIComponent(token)}`,
    );
  },

  setPassword(token: string, password: string) {
    return apiFetch<{ message: string }>("/auth/set-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
  },

  forgotPassword(email: string) {
    return apiFetch<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },
};
