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

/** POST /get_response asking for a server-sent stream, so the reply can be shown
 * as it is written (first words in under a second, instead of the whole reply
 * after several). `onText` receives the reply so far each time it grows.
 *
 * Commands, games and safety replies come back as ordinary JSON even when a
 * stream is asked for; that case calls `onText` once with the whole reply. */
export async function streamChatMessage(
  msg: string,
  conversationId: number | null | undefined,
  onText: (replySoFar: string) => void,
): Promise<string> {
  const body = new URLSearchParams({ msg });
  if (conversationId != null) body.set("conversation_id", String(conversationId));
  const res = await fetch(`${API_BASE}/get_response`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "text/event-stream" },
    body,
  });
  if (!res.ok) throw new Error(`get_response failed: ${res.status}`);

  if (!(res.headers.get("content-type") ?? "").includes("text/event-stream") || !res.body) {
    const data = await res.json();
    const reply: string = data.response ?? "";
    onText(reply);
    return reply;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reply = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const line = block.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let event: { delta?: string; done?: boolean; response?: string };
      try {
        event = JSON.parse(line.slice(5));
      } catch {
        continue;
      }
      if (event.delta) {
        reply += event.delta;
        onText(reply);
      }
      if (event.done && event.response != null) {
        reply = event.response;
        onText(reply);
      }
    }
  }
  return reply;
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

/** `checkin` lets the bot open with a check-in after a long break; only pass it
 * when resuming the latest conversation, never when browsing an old one. */
export async function fetchConversationMessages(id: number, checkin = false): Promise<ChatHistoryItem[]> {
  const res = await fetch(`${API_BASE}/conversations/${id}/messages${checkin ? "?checkin=1" : ""}`, { credentials: "include" });
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
