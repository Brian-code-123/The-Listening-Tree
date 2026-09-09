"use client";

import { useEffect, useState } from "react";
import { fetchCurrentUser } from "./me";

/**
 * Session language for pre-auth pages (login/register) that have no
 * useRequireAuth() gate — /me still returns a lang for an unauthenticated
 * session, so this reads it directly instead of defaulting to "en".
 */
export function useSessionLang() {
  const [lang, setLang] = useState("en");

  useEffect(() => {
    fetchCurrentUser()
      .then((u) => {
        if (u.lang) setLang(u.lang);
      })
      .catch(() => {
        // Stay on "en" if /me can't be reached.
      });
  }, []);

  return lang;
}
