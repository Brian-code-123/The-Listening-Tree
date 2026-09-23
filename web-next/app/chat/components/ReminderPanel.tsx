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
export default function ReminderPanel({ lang, t, translations }: ReminderPanelProps) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [label, setLabel] = useState("");
  const [time, setTime] = useState("");
  const [daily, setDaily] = useState(false);

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
      await createReminder(label.trim(), time, daily ? "daily" : "once");
      setLabel("");
      setTime("");
      setDaily(false);
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
                    {r.repeat === "daily" && <> · <i className="fas fa-repeat" /> {t("reminder_daily", "Every day")}</>}
                  </div>
                </div>
                {r.active && (
                  <button className="reminder-delete" title={t("reminder_delete", "Delete")} onClick={() => handleDelete(r.id)}>
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
            <option value={translations.reminder_preset_1 ?? "Take medicine"}>{translations.reminder_preset_1 ?? "Take medicine"}</option>
            <option value={translations.reminder_preset_2 ?? "Walk"}>{translations.reminder_preset_2 ?? "Walk"}</option>
            <option value={translations.reminder_preset_3 ?? "Drink water"}>{translations.reminder_preset_3 ?? "Drink water"}</option>
            <option value={translations.reminder_preset_4 ?? "Eat meal"}>{translations.reminder_preset_4 ?? "Eat meal"}</option>
            <option value={translations.reminder_preset_5 ?? "Rest"}>{translations.reminder_preset_5 ?? "Rest"}</option>
            <option value={translations.reminder_preset_6 ?? "Exercise"}>{translations.reminder_preset_6 ?? "Exercise"}</option>
          </datalist>
          <input id="reminderTime" type="time" required value={time} onChange={(e) => setTime(e.target.value)} />
          <label className="reminder-repeat">
            <input type="checkbox" checked={daily} onChange={(e) => setDaily(e.target.checked)} />
            {t("reminder_daily", "Repeat every day")}
          </label>
          <button type="submit" aria-label={t("add_reminder_button", "Add reminder")}>
            <i className="fas fa-plus" />
          </button>
        </form>
      </div>
    </div>
  );
}
