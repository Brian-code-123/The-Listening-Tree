"use client";

import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

// Theme lives in localStorage under the same "theme" key the Jinja pages
// use, so switching between a ported page and a not-yet-ported one keeps
// the user's choice.
//
// useSyncExternalStore rather than useState + useEffect: localStorage is
// only readable on the client, so reading it during render would produce
// a server/client hydration mismatch, and reading it in an effect means
// calling setState from an effect body. This hook is the React-provided
// answer for exactly this shape — an external, client-only store — and
// getServerSnapshot pins SSR to "light" so markup matches on first paint.
const listeners = new Set<() => void>();

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  // Also react to another tab changing the theme.
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function getSnapshot(): Theme {
  try {
    return localStorage.getItem("theme") === "dark" ? "dark" : "light";
  } catch {
    // Private-mode / blocked storage — fall back to the default.
    return "light";
  }
}

function getServerSnapshot(): Theme {
  return "light";
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const toggleTheme = useCallback(() => {
    try {
      localStorage.setItem("theme", theme === "dark" ? "light" : "dark");
    } catch {
      // Ignore write failures; the toggle just won't persist.
    }
    listeners.forEach((notify) => notify());
  }, [theme]);

  return { theme, toggleTheme };
}
