import { api } from "./client";

interface BriefingSection {
  title: string;
  content: string;
  source: string;
}

export interface BriefingResponse {
  sections: BriefingSection[];
  generated_at: string;
  summary: string;
}

export async function fetchBriefing(): Promise<BriefingResponse> {
  return api<BriefingResponse>("/briefing");
}
