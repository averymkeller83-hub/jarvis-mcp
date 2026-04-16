import { api } from "./client";

interface SetupProgress {
  status: string;
  current_step: number;
  total_steps: number;
  started_at: string;
}

export async function startSetup(): Promise<SetupProgress> {
  return api<SetupProgress>("/setup/start", { method: "POST" });
}

export async function submitStep(
  step: number,
  config: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return api(`/setup/step/${step}`, {
    method: "POST",
    body: JSON.stringify({ config }),
  });
}

export async function skipStep(
  step: number,
): Promise<Record<string, unknown>> {
  return api(`/setup/skip/${step}`, { method: "POST" });
}

export async function fetchProgress(): Promise<SetupProgress> {
  return api<SetupProgress>("/setup/progress");
}
