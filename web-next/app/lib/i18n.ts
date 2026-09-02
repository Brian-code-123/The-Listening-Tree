"use client";

import { useEffect, useState } from "react";
import { fetchTranslations, type Translations } from "./translations";

/**
 * Fetches GET /translations/{lang} once per mount and exposes a t(key,
 * fallback) helper — the shared replacement for each page hand-rolling
 * its own window.X_I18N object. Every ported page (register/login/
 * profile/accessibility/hk_guide/chat) uses this instead of a bespoke
 * translation loader.
 */
export function useTranslations(lang: string = "en") {
  const [translations, setTranslations] = useState<Translations>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchTranslations(lang)
      .then((data) => {
        if (!cancelled) setTranslations(data);
      })
      .catch(() => {
        // Swallow — t() below falls back to each call site's own default,
        // matching the old Jinja `translations.x if translations else
        // "..."` behavior when `translations` was falsy.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lang]);

  function t(key: string, fallback: string): string {
    return translations[key] ?? fallback;
  }

  return { t, translations, loading };
}
