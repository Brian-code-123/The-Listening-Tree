"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "./api";
import { fetchCurrentUser, type CurrentUser } from "./me";

/**
 * Shared auth-gate for pages that require a logged-in session
 * (/profile, /accessibility, /chat) — checks GET /me once on mount and
 * redirects to the backend's /login if not authenticated, matching each
 * Jinja route's own `if uid is None: redirect("/login")` behavior.
 */
export function useRequireAuth() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((u) => {
        if (cancelled) return;
        if (!u.authenticated) {
          window.location.href = `${API_BASE}/login`;
          return;
        }
        setUser(u);
      })
      .catch(() => {
        if (!cancelled) window.location.href = `${API_BASE}/login`;
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, checking };
}
