"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../../lib/api";
import { syncNativeReminders } from "../../lib/capacitor";
import { createReminder, deleteReminder, fetchReminders, type Reminder } from "../../lib/reminders";
import type { Translations } from "../../lib/translations";

interface ReminderPanelProps {
  lang: string;
  translations: Translations;
  t: (key: string, fallback: string) => string;
}

// Two independent polling loops, same as the original (checkReminders
// every 60s for the UI list; a separately phase-aligned
// checkForRemindersNow for the alarm/sound trigger) — deliberately not
// merged, since they're different concerns (list refresh vs. alarm).
export default function ReminderPanel({ lang, t }: ReminderPanelProps) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [label, setLabel] = useState("");
  const [time, setTime] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const firedForRef = useRef<Set<string>>(new Set());

  // Promise-callback form (rather than await) so setState never runs
  // synchronously in the mount effect's body below.
  function refreshList() {
    return fetchReminders()
      .then((list) => {
        setReminders(list);
        syncNativeReminders(list, lang).catch(() => {});
      })
      .catch(() => {
        // Leave the existing list as-is on a transient fetch failure.
      });
  }

  async function checkAlarms() {
    let list: Reminder[];
    try {
      list = await fetchReminders();
    } catch {
      return;
    }
    const currentTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    for (const r of list) {
      const key = `${r.id}:${currentTime}`;
      if (r.time === currentTime && r.active && !firedForRef.current.has(key)) {
        firedForRef.current.add(key);
        const audio = new Audio(`${API_BASE}/static/notification.mp3`);
        audio.loop = true;
        audio.play().catch(() => {});
        audioRef.current = audio;
        setTimeout(() => {
          const message =
            lang === "zh-HK" ? `⏰ 提醒：${r.label}！\n\n係時候${r.label}喇！` : `⏰ Reminder: ${r.label}!\n\nIt's time to ${r.label.toLowerCase()}!`;
          alert(message);
          audio.pause();
          audio.currentTime = 0;
          deleteReminder(r.id)
            .catch(() => {})
            .finally(refreshList);
        }, 300);
      }
    }
  }

  // Both loops are declared after the functions they call so the lint
  // rule can see the definitions — same two-independent-timers structure
  // as the original, just ordered for the analyzer.
  useEffect(() => {
    refreshList();
    const interval = setInterval(refreshList, 60000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Alarm-check loop: phase-aligned to the top of the next minute, then
  // every 60s after that — matches the original's setTimeout-then-
  // setInterval pattern.
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    const now = new Date();
    const timeout = setTimeout(() => {
      checkAlarms();
      interval = setInterval(checkAlarms, 60000);
    }, (60 - now.getSeconds()) * 1000);
    return () => {
      clearTimeout(timeout);
      if (interval) clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim() || !time) return;
    try {
      await createReminder(label.trim(), time);
      setLabel("");
      setTime("");
      refreshList();
    } catch {
      // Swallow — matches original's lack of an explicit error UI here.
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteReminder(id);
      refreshList();
    } catch {
      // Same as above.
    }
  }

  return (
    <div className="sidebar-card reminder-card">
      <div className="sidebar-card-header">
        <i className="fas fa-bell" /> {t("todays_reminders", "Today's Reminders")}
      </div>
      <div className="sidebar-card-body">
        <div id="reminderList">
          {reminders.length === 0 ? (
            <p style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem", padding: "8px 0" }}>
              {t("no_reminders", "No active reminders")}
            </p>
          ) : (
            reminders.map((r) => (
              <div key={r.id} className={`reminder-item${r.active ? "" : " inactive"} fade-in`}>
                <div className="reminder-icon">
                  <i className="fas fa-bell" />
                </div>
                <div className="reminder-info">
                  <div className="reminder-label">{r.label}</div>
                  <div className="reminder-time-badge">
                    <i className="fas fa-clock" /> {r.time}
                  </div>
                </div>
                {r.active && (
                  <button className="reminder-delete" title="Delete" onClick={() => handleDelete(r.id)}>
                    <i className="fas fa-times" />
                  </button>
                )}
              </div>
            ))
          )}
        </div>
        <form className="add-reminder-form" onSubmit={handleAdd}>
          <input
            type="text"
            placeholder={t("reminder_label", "What to remind")}
            required
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            list="reminderPresets"
          />
          <datalist id="reminderPresets">
            <option value="Take medicine">Take medicine</option>
            <option value="Walk">Walk</option>
            <option value="Drink water">Drink water</option>
            <option value="Eat meal">Eat meal</option>
            <option value="Rest">Rest</option>
            <option value="Exercise">Exercise</option>
          </datalist>
          <input type="time" required value={time} onChange={(e) => setTime(e.target.value)} />
          <button type="submit">
            <i className="fas fa-plus" />
          </button>
        </form>
      </div>
    </div>
  );
}
