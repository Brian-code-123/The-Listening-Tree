import { API_BASE } from "./api";

export type Translations = Record<string, string>;

export async function fetchTranslations(lang: string): Promise<Translations> {
  const res = await fetch(`${API_BASE}/translations/${lang}`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(`translations fetch failed: ${res.status}`);
  }
  return res.json() as Promise<Translations>;
}

// Ported from app/core/config.py's CONVERSATION_TAGS (repo root) — a
// small, fixed, rarely-changing design constant, not user data, so it's
// duplicated here rather than adding a second backend endpoint just for
// it. Keep in sync by hand if that dict ever changes. Labels for these
// keys come from the /translations/{lang} endpoint (`tag_<key>`), not
// from here.
export const CONVERSATION_TAGS: Record<string, { icon: string; color: string }> = {
  family: { icon: "fa-people-roof", color: "#5B8DEF" },
  friends: { icon: "fa-user-friends", color: "#F2CC8F" },
  health: { icon: "fa-heart-pulse", color: "#5B9A7D" },
  daily: { icon: "fa-sun", color: "#98A2B3" },
  important: { icon: "fa-star", color: "#E07A5F" },
};
