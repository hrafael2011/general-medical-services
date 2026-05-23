import { apiFetch } from "./client";

interface FeatureFlags {
  notifications: boolean;
  telegram: boolean;
  confirmations: boolean;
}

export function fetchFeatureFlags(): Promise<FeatureFlags> {
  return apiFetch<FeatureFlags>("/feature-flags");
}
