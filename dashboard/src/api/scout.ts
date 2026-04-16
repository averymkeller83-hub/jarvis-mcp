import { api } from "./client";

export interface ScoutSource {
  name: string;
  enabled: boolean;
  cadence: string;
  description: string;
}

export interface ScoutFind {
  title: string;
  url: string;
  source: string;
  relevance: number;
  summary: string;
  candidate_id: string;
}

interface SourcesResponse {
  sources: ScoutSource[];
  count: number;
}

interface DiscoverResponse {
  finds: ScoutFind[];
  scanned_at: string;
}

export async function fetchScoutSources(): Promise<SourcesResponse> {
  return api<SourcesResponse>("/scout/sources");
}

export async function runDiscovery(): Promise<DiscoverResponse> {
  return api<DiscoverResponse>("/scout/discover", { method: "POST" });
}

export async function installCandidate(
  candidateId: string,
): Promise<Record<string, unknown>> {
  return api("/scout/install", {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export async function dismissCandidate(
  candidateId: string,
  reason?: string,
): Promise<void> {
  await api("/scout/dismiss", {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId, reason }),
  });
}
