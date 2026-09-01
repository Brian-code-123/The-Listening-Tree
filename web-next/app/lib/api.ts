// Talks to the FastAPI backend running locally on port 5000. This POC is
// local-dev-only (see docs/FRONTEND_ROADMAP.md and the SDLC plan) — the
// base URL is hardcoded rather than configurable since there's no
// deployed target yet.
export const API_BASE = "http://localhost:5000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    // Required for the lt_session cookie (set by logging in at
    // localhost:5000/login) to be sent along with cross-port requests from
    // localhost:3001 — see the CORS allowlist in app/main.py at the repo
    // root, which explicitly permits this origin with allow_credentials.
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

function formBody(fields: Record<string, string>): URLSearchParams {
  return new URLSearchParams(fields);
}

export interface Conversation {
  id: number;
  title: string;
  updated_at: string;
  pinned: boolean;
  tag: string | null;
}

export function fetchConversations(): Promise<{ conversations: Conversation[] }> {
  return request("/conversations");
}

export function togglePin(id: number): Promise<{ pinned: boolean }> {
  return request(`/conversations/${id}/pin`, { method: "POST" });
}

export function renameConversation(id: number, title: string): Promise<{ title: string }> {
  return request(`/conversations/${id}/title`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formBody({ title }),
  });
}

export function setConversationTag(id: number, tag: string): Promise<{ tag: string | null }> {
  return request(`/conversations/${id}/tag`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formBody({ tag }),
  });
}
