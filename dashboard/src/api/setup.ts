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

interface SetupStatus {
  setup_complete: boolean;
  completed_at?: string;
}

export async function fetchSetupStatus(): Promise<SetupStatus> {
  return api<SetupStatus>("/setup/status");
}

interface VerifyResult {
  ok: boolean;
  error?: string;
  bot_name?: string;
  bot_valid?: boolean;
  channel_name?: string;
  team?: string;
  target?: string;
  type?: string;
  [key: string]: unknown;
}

export async function verifyChannel(
  channel: string,
  credentials: Record<string, string>,
): Promise<VerifyResult> {
  return api<VerifyResult>("/setup/verify", {
    method: "POST",
    body: JSON.stringify({ channel, credentials }),
  });
}

interface TestMessageResult {
  ok: boolean;
  message?: string;
  error?: string;
}

export async function sendTestMessage(
  channel: string,
  credentials: Record<string, string>,
): Promise<TestMessageResult> {
  return api<TestMessageResult>("/setup/test-message", {
    method: "POST",
    body: JSON.stringify({ channel, credentials }),
  });
}
