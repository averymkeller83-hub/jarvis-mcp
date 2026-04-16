import { api } from "./client";

export interface HistoryEvent {
  event: string;
  data: Record<string, unknown>;
  source: string;
  timestamp: string;
}

interface EventsHistoryResponse {
  events: HistoryEvent[];
  count: number;
}

export async function fetchEventHistory(
  source?: string,
  limit: number = 50,
): Promise<EventsHistoryResponse> {
  const params = new URLSearchParams();
  if (source) params.set("source", source);
  params.set("limit", String(limit));
  return api<EventsHistoryResponse>(`/events/history?${params}`);
}
