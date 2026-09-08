"use client";

import { useEffect, useState } from "react";
import { syncNativeReminders } from "../../lib/capacitor";
import { createReminder, deleteReminder, fetchReminders, type Reminder } from "../../lib/reminders";
import type { Translations } from "../../lib/translations";

interface ReminderPanelProps {
  lang: string;
  translations: Translations;
  t: (key: string, fallback: string) => string;
}

// This panel only refreshes its own list every 60s. The alarm/sound
// trigger used to live here too, but that meant it only fired while
// /chat was open — it now lives in app/components/ReminderAlarm.tsx,
// mounted site-wide in the root layout.
export default function ReminderPanel({ lang, t }: ReminderPanelProps) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [label, setLabel] = useState("");
  const [time, setTime] = useState("");

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

  useEffect(() => {
    refreshList();
    const interval = setInterval(refreshList, 60000);
    return () => clearInterval(interval);
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
            id="reminderLabel"
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
          <input id="reminderTime" type="time" required value={time} onChange={(e) => setTime(e.target.value)} />
          <button type="submit">
            <i className="fas fa-plus" />
          </button>
        </form>
      </div>
    </div>
  );
}
