import { api } from "./client";

export interface ChatResponse {
  surface: string;
  reply: string;
  success?: boolean;
  action?: string;
  data?: Record<string, unknown>;
}

export async function sendMessage(message: string): Promise<ChatResponse> {
  return api<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export interface ServerMessage {
  role: string;
  text: string;
  surface?: string;
  timestamp: string;
}

interface ChatHistoryResponse {
  messages: ServerMessage[];
  count: number;
}

export async function fetchChatHistory(limit = 100): Promise<ChatHistoryResponse> {
  return api<ChatHistoryResponse>(`/chat/history?limit=${limit}`);
}

export async function clearChatHistory(): Promise<void> {
  await api("/chat/history", { method: "DELETE" });
}
