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

  inviteUser(userId: string) {
    return apiFetch<{ message: string; email: string }>(`/admin/users/${userId}/invite`, {
      method: "POST",
    });
  },

  sendReset(userId: string) {
    return apiFetch<{ message: string; email: string }>(`/admin/users/${userId}/send-reset`, {
      method: "POST",
    });
  },

  deleteUser(id: string) {
    return apiFetch<void>(`/admin/users/${id}`, { method: "DELETE" });
  },

  updateUser(id: string, payload: { name?: string; role?: string; active?: boolean }) {
    return apiFetch<UserRead>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};
