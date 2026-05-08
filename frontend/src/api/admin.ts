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
};
