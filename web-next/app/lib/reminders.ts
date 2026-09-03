import { API_BASE } from "./api";

export interface Reminder {
  id: number;
  label: string;
  time: string;
  active: boolean;
}

export async function fetchReminders(): Promise<Reminder[]> {
  const res = await fetch(`${API_BASE}/get_reminders`, { credentials: "include" });
  if (!res.ok) throw new Error(`get_reminders failed: ${res.status}`);
  const data = await res.json();
  return data.reminders ?? [];
}

export async function createReminder(label: string, time: string): Promise<Reminder> {
  const res = await fetch(`${API_BASE}/reminders`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ label, time }),
  });
  const body = await res.json();
  if (!res.ok || !body.success) {
    throw new Error(body.message || `create reminder failed: ${res.status}`);
  }
  return { id: body.id, label: body.label, time: body.time, active: true };
}

export async function deleteReminder(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/reminders/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message || `delete reminder failed: ${res.status}`);
  }
}
