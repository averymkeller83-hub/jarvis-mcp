import { api } from "./client";

interface EngineStatus {
  running: boolean;
  task_count: number;
}

export async function fetchEngineStatus(): Promise<EngineStatus> {
  return api<EngineStatus>("/engine/status");
}

export async function fetchSchedule(): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>("/engine/schedule");
}

export async function startEngine(): Promise<void> {
  await api("/engine/start", { method: "POST" });
}

export async function stopEngine(): Promise<void> {
  await api("/engine/stop", { method: "POST" });
}

export async function runTask(
  name: string,
): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/engine/run/${name}`, {
    method: "POST",
  });
}
