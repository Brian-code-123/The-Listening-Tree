import { API_BASE } from "./api";

export interface ChatHistoryItem {
  timestamp: string;
  sender: "user" | "bot";
  message: string;
}

/** GET /get_chat_history — the legacy "most recent conversation" log,
 * used by /accessibility (and, later, /chat's non-deep-link default
 * load). Shared here so both pages call the same thing the same way. */
export async function fetchChatHistory(): Promise<ChatHistoryItem[]> {
  const res = await fetch(`${API_BASE}/get_chat_history`, { credentials: "include" });
  if (!res.ok) throw new Error(`get_chat_history failed: ${res.status}`);
  const data = await res.json();
  return data.history ?? [];
}

/** POST /get_response — send a chat message, optionally scoped to a
 * conversation_id. Returns the bot's reply text. */
export async function sendChatMessage(msg: string, conversationId?: number): Promise<string> {
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
