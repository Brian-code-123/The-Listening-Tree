import { API_BASE } from "./api";

export interface ClientConfig {
  google_enabled: boolean;
}

export async function fetchConfig(): Promise<ClientConfig> {
  const res = await fetch(`${API_BASE}/config`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`config fetch failed: ${res.status}`);
  }
  return res.json() as Promise<ClientConfig>;
}
