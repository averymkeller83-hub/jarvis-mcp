import { api } from "./client";

export interface ScoutSource {
  name: string;
  enabled: boolean;
  cadence: string;
  description: string;
}

export interface ScoutFind {
  candidate_id: string;
  name: string;
  pitch: string;
  source_badge: string;
  match_reason: string;
  sandbox_status: string;
  install_available: boolean;
  details: {
    relevance_score: number;
    candidate_type: string;
    source_url: string;
    metadata: Record<string, unknown>;
  };
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
