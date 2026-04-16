import { api, setTokens, clearTokens } from "./client";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

interface UserInfo {
  username: string;
  role: string;
}

interface RegisterResult {
  username: string;
  role: string;
  created_at: string;
}

export async function register(
  username: string,
  password: string,
): Promise<RegisterResult> {
  return api<RegisterResult>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function login(
  username: string,
  password: string,
): Promise<void> {
  const tokens = await api<AuthTokens>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setTokens(tokens.access_token, tokens.refresh_token);
}

export async function fetchMe(): Promise<UserInfo> {
  return api<UserInfo>("/auth/me");
}

export function logout(): void {
  clearTokens();
}
