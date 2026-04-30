import { apiFetch } from "./client";

export interface TelegramUserLinkRead {
  id: string;
  telegram_user_id: string;
  telegram_username: string | null;
  user_id: string;
  active: boolean;
  linked_by: string | null;
  linked_at: string;
  last_used_at: string | null;
}

export interface CreateTelegramLinkRequest {
  telegram_user_id: string;
  telegram_username?: string | null;
  user_id: string;
}

export interface TelegramLinkListResponse {
  items: TelegramUserLinkRead[];
  total: number;
}

export const telegramApi = {
  listLinks(): Promise<TelegramLinkListResponse> {
    return apiFetch<TelegramLinkListResponse>("/telegram/links");
  },

  createLink(data: CreateTelegramLinkRequest): Promise<TelegramUserLinkRead> {
    return apiFetch<TelegramUserLinkRead>("/telegram/links", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  deleteLink(id: string): Promise<void> {
    return apiFetch<void>(`/telegram/links/${id}`, {
      method: "DELETE",
    });
  },
};
