import { API_BASE } from "./api";

export interface CurrentUser {
  authenticated: boolean;
  display_name?: string;
  email?: string;
}

/** GET /me — session identity check + basic user info. Never throws on a
 * 401 (not logged in) — that's a normal, expected response shape here,
 * not an error. */
export async function fetchCurrentUser(): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/me`, { credentials: "include" });
  if (res.status === 401) {
    return { authenticated: false };
  }
  if (!res.ok) {
    throw new Error(`/me fetch failed: ${res.status}`);
  }
  return res.json() as Promise<CurrentUser>;
}
