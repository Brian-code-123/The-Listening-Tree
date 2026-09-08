"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import { fetchCurrentUser } from "../lib/me";
import { deleteReminder, fetchReminders, type Reminder } from "../lib/reminders";

// Site-wide reminder alarm: fires regardless of which page is open, not
// just /chat — the previous version lived inside ReminderPanel, so a
// reminder due while the user was on /history or /hk_guide silently did
// nothing. Phase-aligned to the next minute boundary, then every 60s,
// same cadence as the original. Audio keeps looping until the user
// dismisses the blocking alert() — that's the "press confirm to stop
// the music" behavior, unchanged from the original implementation.
//
// Known limitation: this mounts per-tab (root layout), so a user with
// two tabs open (e.g. one on /chat, one on /history) gets the alarm
// fired independently in each — two overlapping sounds, two alerts.
// Not addressed here; would need cross-tab coordination (BroadcastChannel
// or a localStorage lock) to fix.
export default function ReminderAlarm() {
  const [lang, setLang] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const firedForRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((u) => {
        if (!cancelled && u.authenticated) setLang(u.lang ?? "en");
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (lang === null) return;

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
          // 300ms so audio.play() has started before the blocking alert()
          // freezes the tab — this delay is inherited unexplained from the
          // original jQuery implementation (static/chat.js), kept as-is.
          setTimeout(() => {
            const message =
              lang === "zh-HK" ? `⏰ 提醒：${r.label}！\n\n係時候${r.label}喇！` : `⏰ Reminder: ${r.label}!\n\nIt's time to ${r.label.toLowerCase()}!`;
            alert(message);
            audio.pause();
            audio.currentTime = 0;
            deleteReminder(r.id).catch(() => {});
          }, 300);
        }
      }
    }

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
  }, [lang]);

  return null;
}
