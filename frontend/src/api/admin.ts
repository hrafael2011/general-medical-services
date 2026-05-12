import { apiFetch } from "./client";

export interface UserRead {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
  must_change_password: boolean;
}

export const adminApi = {
  listUsers(role?: string): Promise<UserRead[]> {
    const query = role ? `?role=${role}` : "";
    return apiFetch<UserRead[]>(`/admin/users${query}`);
  },

  createEncargado(name: string, email: string, temporaryPassword?: string) {
    return apiFetch<{ user: UserRead; temporary_password: string }>("/admin/users/encargados", {
      method: "POST",
      body: JSON.stringify({ name, email, temporary_password: temporaryPassword }),
    });
  },

  resetPassword(userId: string, temporaryPassword?: string) {
    return apiFetch<{ user: UserRead; temporary_password: string }>(
      `/admin/users/${userId}/reset-password`,
      {
        method: "POST",
        body: JSON.stringify({ temporary_password: temporaryPassword }),
      },
    );
  },
};
