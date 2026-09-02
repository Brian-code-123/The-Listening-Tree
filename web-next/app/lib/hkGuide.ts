import { API_BASE } from "./api";

export interface HkGuideItem {
  category: "food" | "shopping" | "fun" | "events";
  name: string;
  short_desc: string;
  full_desc?: string;
  location?: string;
  price_range?: string;
  hours?: string;
  transport?: string;
  elderly_friendly?: boolean;
  tips?: string[];
  url?: string;
}

export interface HkGuideResponse {
  items: HkGuideItem[];
  last_updated: string;
  total: number;
}

export async function fetchHkGuide(refresh = false): Promise<HkGuideResponse> {
  const res = await fetch(`${API_BASE}/get_hk_guide${refresh ? "?refresh=1" : ""}`, { credentials: "include" });
  if (!res.ok) throw new Error(`get_hk_guide failed: ${res.status}`);
  return res.json() as Promise<HkGuideResponse>;
}

export const CATEGORY_ICON: Record<string, string> = {
  food: "fa-utensils",
  shopping: "fa-shopping-bag",
  fun: "fa-theater-masks",
  events: "fa-calendar-star",
};

export const CATEGORY_COLOR: Record<string, string> = {
  food: "#E07A5F",
  shopping: "#5B8DEF",
  fun: "#5B9A7D",
  events: "#F2CC8F",
};
