// In production this app is deployed as a Vercel `services` route
// alongside the FastAPI app under the same origin (see vercel.json at the
// repo root) — same-origin means a relative/empty base is correct there.
// Locally the two run as separate dev servers on different ports, so
// NEXT_PUBLIC_API_BASE (set in web-next/.env.local, gitignored) points
// this at the FastAPI dev server instead.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    // Same-origin in production, so this is a no-op there — kept for local
    // dev, where it's required for the lt_session cookie (set by logging
    // in at localhost:5000/login) to cross ports to localhost:3001. See
    // the CORS allowlist in app/main.py at the repo root.
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
