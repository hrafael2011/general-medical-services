import { apiFetch } from "./client";

interface FeatureFlags {
  notifications: boolean;
  telegram: boolean;
}

export function fetchFeatureFlags(): Promise<FeatureFlags> {
  return apiFetch<FeatureFlags>("/feature-flags");
}
