import { api } from "./client";

export async function fetchSettings(): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>("/settings");
}

export async function updateSection(
  section: string,
  data: Record<string, unknown>,
): Promise<void> {
  await api(`/settings/${section}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function fetchNotifications(): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>("/settings/notifications");
}

export async function updateNotifications(
  data: Record<string, unknown>,
): Promise<void> {
  await api("/settings/notifications", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function fetchControlTiers(): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>("/settings/control-tiers");
}

export async function updateControlTiers(
  data: Record<string, unknown>,
): Promise<void> {
  await api("/settings/control-tiers", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function exportData(): Promise<{ path: string }> {
  return api<{ path: string }>("/settings/export", { method: "POST" });
}
