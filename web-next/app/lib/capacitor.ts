// Capacitor mobile bridge — ported from the top of static/chat.js's
// inline Capacitor block. Everything here is guarded by `window.Capacitor`
// exactly as the original does, so it no-ops cleanly in a plain browser
// (which is all this local port has been verified against — the native
// mobile app loads the deployed URL directly per capacitor.config.ts, so
// this code path only actually runs there, same as the original).
import type { LocalNotificationsPlugin } from "@capacitor/local-notifications";

import type { Reminder } from "./reminders";

declare global {
  interface Window {
    Capacitor?: unknown;
    // The real plugin type rather than a hand-written structural stand-in —
    // a narrower local shape can't accept the plugin's own `schedule`
    // signature (parameter types are contravariant), which is what the
    // stand-in version tripped over.
    __localNotifications?: LocalNotificationsPlugin;
  }
}

export function initCapacitorBridge(): void {
  if (typeof window === "undefined" || !window.Capacitor) return;

  document.body.classList.add("capacitor-app");
  document.documentElement.classList.add("capacitor-app");

  import("@capacitor/app")
    .then(({ App }) => {
      App.addListener("backButton", ({ canGoBack }) => {
        if (canGoBack) window.history.back();
        else App.exitApp();
      });
    })
    .catch(() => {});

  import("@capacitor/keyboard")
    .then(({ Keyboard }) => {
      Keyboard.addListener("keyboardWillShow", (info) => {
        document.body.style.setProperty("--keyboard-height", `${info.keyboardHeight}px`);
        document.body.classList.add("keyboard-open");
      });
      Keyboard.addListener("keyboardWillHide", () => {
        document.body.style.setProperty("--keyboard-height", "0px");
        document.body.classList.remove("keyboard-open");
      });
    })
    .catch(() => {});

  import("@capacitor/haptics")
    .then(({ Haptics, ImpactStyle }) => {
      document.addEventListener("click", (e) => {
        if ((e.target as HTMLElement)?.closest(".send_btn, .chat-nav-btn, .reminder-delete")) {
          Haptics.impact({ style: ImpactStyle.Light }).catch(() => {});
        }
      });
    })
    .catch(() => {});

  import("@capacitor/splash-screen")
    .then(({ SplashScreen }) => SplashScreen.hide())
    .catch(() => {});

  import("@capacitor/status-bar")
    .then(({ StatusBar }) => {
      const sync = () => {
        const theme = document.body.getAttribute("data-theme") || "light";
        StatusBar.setStyle({ style: theme === "dark" ? ("DARK" as never) : ("LIGHT" as never) }).catch(() => {});
        StatusBar.setBackgroundColor({ color: theme === "dark" ? "#0F1923" : "#5B9A7D" }).catch(() => {});
      };
      sync();
      new MutationObserver(sync).observe(document.body, { attributes: true, attributeFilter: ["data-theme"] });
    })
    .catch(() => {});

  import("@capacitor/local-notifications")
    .then(({ LocalNotifications }) => {
      window.__localNotifications = LocalNotifications;
      LocalNotifications.requestPermissions().catch(() => {});
    })
    .catch(() => {});
}

/** Reschedule native OS notifications to match the current active
 * reminder list — called after every reminder-list refresh, same as the
 * original's window.syncNativeReminders. */
export async function syncNativeReminders(reminders: Reminder[], lang: string): Promise<void> {
  const LocalNotifications = window.__localNotifications;
  if (!LocalNotifications) return;
  try {
    const { notifications } = await LocalNotifications.getPending();
    if (notifications.length) {
      await LocalNotifications.cancel({ notifications: notifications.map((n) => ({ id: n.id })) });
    }
    const active = reminders.filter((r) => r.active && /^\d{1,2}:\d{2}$/.test(r.time));
    if (!active.length) return;
    const toSchedule = active.map((r, i) => {
      const [h, m] = r.time.split(":").map(Number);
      const when = new Date();
      when.setHours(h, m, 0, 0);
      if (when <= new Date()) when.setDate(when.getDate() + 1);
      return {
        id: i + 1,
        title: lang === "zh-HK" ? "⏰ 提醒" : "⏰ Reminder",
        body: r.label,
        schedule: { at: when },
        sound: "notification.mp3",
      };
    });
    await LocalNotifications.schedule({ notifications: toSchedule });
  } catch {
    // Matches the original's blanket .catch(() => {}) on every step here.
  }
}
