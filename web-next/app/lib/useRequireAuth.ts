"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "./api";
import { fetchCurrentUser, type CurrentUser } from "./me";

/**
 * Shared auth-gate for pages that require a logged-in session
 * (/profile, /accessibility, /chat) — checks GET /me once on mount and
 * redirects to /login if not authenticated, matching each Jinja route's
 * own `if uid is None: redirect("/login")` behavior.
 *
 * Same-origin (production), /login is another page of this app, so route
 * client-side: a full document load would re-download and re-hydrate
 * everything just to show a form. Only when the API (and its /login) is on
 * another origin — local dev — is a full navigation needed.
 */
export function useRequireAuth() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const goToLogin = () => {
      if (API_BASE) {
        // Another origin (or path prefix): a full navigation is the only way there.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = `${API_BASE}/login`;
      } else {
        router.replace("/login");
      }
    };
    fetchCurrentUser()
      .then((u) => {
        if (cancelled) return;
        if (!u.authenticated) {
          goToLogin();
          return;
        }
        setUser(u);
      })
      .catch(() => {
        if (!cancelled) goToLogin();
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return { user, checking };
}
