import { API_BASE } from "./api";

export interface CurrentUser {
  authenticated: boolean;
  display_name?: string;
  email?: string;
  /** Session language ("en" | "zh-HK") — drives TTS voice, calendar
   * locale, and which language button renders as active. */
  lang?: string;
}

let inFlight: Promise<CurrentUser> | null = null;

/** GET /me — session identity check + basic user info. Never throws on a
 * 401 (not logged in) — that's a normal, expected response shape here,
 * not an error. The 401 body still carries the session `lang`, which the
 * logged-out login/register pages need.
 *
 * Callers that overlap share one request: several components ask for /me
 * on the same mount, and each extra request can cold-start its own
 * serverless instance. Only the in-flight request is shared — nothing is
 * cached once it settles, so a login or logout is always seen. */
export function fetchCurrentUser(): Promise<CurrentUser> {
  inFlight ??= requestCurrentUser().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function requestCurrentUser(): Promise<CurrentUser> {
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
