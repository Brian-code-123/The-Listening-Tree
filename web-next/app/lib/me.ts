import { API_BASE } from "./api";

export interface CurrentUser {
  authenticated: boolean;
  display_name?: string;
  email?: string;
  /** Session language ("en" | "zh-HK") — drives TTS voice, calendar
   * locale, and which language button renders as active. */
  lang?: string;
}

/** GET /me — session identity check + basic user info. Never throws on a
 * 401 (not logged in) — that's a normal, expected response shape here,
 * not an error. The 401 body still carries the session `lang`, which the
 * logged-out login/register pages need. */
export async function fetchCurrentUser(): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/me`, { credentials: "include" });
  if (res.status === 401) {
    const body = (await res.json().catch(() => ({}))) as { lang?: string };
    return { authenticated: false, lang: body.lang };
  }
  if (!res.ok) {
    throw new Error(`/me fetch failed: ${res.status}`);
  }
  return res.json() as Promise<CurrentUser>;
}
