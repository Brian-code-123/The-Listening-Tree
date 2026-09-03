import { API_BASE } from "./api";

export interface ChatHistoryItem {
  timestamp: string;
  sender: "user" | "bot";
  message: string;
}

/** GET /get_chat_history — the legacy "most recent conversation" log,
 * used by /accessibility and as /chat's fallback when there's no
 * ?conversation_id= deep link and no existing conversation to open. */
export async function fetchChatHistory(): Promise<ChatHistoryItem[]> {
  const res = await fetch(`${API_BASE}/get_chat_history`, { credentials: "include" });
  if (!res.ok) throw new Error(`get_chat_history failed: ${res.status}`);
  const data = await res.json();
  return data.history ?? [];
}

/** POST /get_response — send a chat message, optionally scoped to a
 * conversation_id. Returns the bot's reply text. */
export async function sendChatMessage(msg: string, conversationId?: number | null): Promise<string> {
  const body = new URLSearchParams({ msg });
  if (conversationId != null) body.set("conversation_id", String(conversationId));
  const res = await fetch(`${API_BASE}/get_response`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error(`get_response failed: ${res.status}`);
  const data = await res.json();
  return data.response ?? "";
}

export interface ConversationSummary {
  id: number;
  title: string;
  updated_at: string;
  pinned: boolean;
  tag: string | null;
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/conversations`, { credentials: "include" });
  if (!res.ok) throw new Error(`conversations failed: ${res.status}`);
  const data = await res.json();
  return data.conversations ?? [];
}

export async function createConversation(): Promise<number> {
  const res = await fetch(`${API_BASE}/conversations/new`, { method: "POST", credentials: "include" });
  if (!res.ok) throw new Error(`conversations/new failed: ${res.status}`);
  const data = await res.json();
  return data.conversation_id;
}

export async function fetchConversationMessages(id: number): Promise<ChatHistoryItem[]> {
  const res = await fetch(`${API_BASE}/conversations/${id}/messages`, { credentials: "include" });
  if (!res.ok) throw new Error(`conversation messages failed: ${res.status}`);
  const data = await res.json();
  return data.history ?? [];
}

export interface NewsArticle {
  title: string;
  description: string;
  source: string;
  url: string;
}

export async function fetchNews(): Promise<NewsArticle[]> {
  const res = await fetch(`${API_BASE}/get_news`, { credentials: "include" });
  if (!res.ok) throw new Error(`get_news failed: ${res.status}`);
  const data = await res.json();
  return data.articles ?? [];
}

export interface HkHoliday {
  title: string;
  start: string;
  allDay: boolean;
  color?: string;
  textColor?: string;
}

export async function fetchHkHolidays(): Promise<HkHoliday[]> {
  const res = await fetch(`${API_BASE}/get_hk_holidays`, { credentials: "include" });
  if (!res.ok) throw new Error(`get_hk_holidays failed: ${res.status}`);
  const data = await res.json();
  return data.holidays ?? [];
}
