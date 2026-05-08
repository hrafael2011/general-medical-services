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

export interface CreateLinkTokenResponse {
  link_token: string;
  deep_link_url: string;
  expires_at: string;
}

export interface LinkTokenRead {
  id: string;
  token: string;
  user_id: string;
  created_by: string | null;
  created_at: string;
  expires_at: string;
  used_at: string | null;
  active: boolean;
}

export const telegramApi = {
  listLinks(): Promise<TelegramUserLinkRead[]> {
    return apiFetch<TelegramUserLinkRead[]>("/telegram/links");
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

  generateLinkToken(userId: string): Promise<CreateLinkTokenResponse> {
    return apiFetch<CreateLinkTokenResponse>("/telegram/link-tokens", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    });
  },

  listLinkTokens(): Promise<LinkTokenRead[]> {
    return apiFetch<LinkTokenRead[]>("/telegram/link-tokens");
  },
};
