import { api } from "./client";

export interface Agent {
  name: string;
  status: string;
  type: string;
  permissions: string[];
  schedule: string | null;
  triggers: string[];
}

interface AgentsResponse {
  agents: Agent[];
  count: number;
}

export async function fetchAgents(): Promise<AgentsResponse> {
  return api<AgentsResponse>("/agents");
}

export async function fetchAgentDetail(name: string): Promise<Agent> {
  return api<Agent>(`/agents/${name}`);
}

export async function fetchAgentContext(
  name: string,
): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/agents/${name}/context`);
}

export async function runAgent(
  name: string,
  params: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/agents/${name}/run`, {
    method: "POST",
    body: JSON.stringify({ params }),
  });
}

export async function approveAgent(name: string): Promise<void> {
  await api(`/agents/${name}/approve`, { method: "PUT" });
}

export async function stopAgent(name: string): Promise<void> {
  await api(`/agents/${name}/stop`, { method: "POST" });
}

export async function startAgent(name: string): Promise<void> {
  await api(`/agents/${name}/start`, { method: "POST" });
}
