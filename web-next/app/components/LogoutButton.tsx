"use client";

import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "../lib/api";
import { logout } from "../lib/auth";

/**
 * Sign-out control. A button that POSTs, not a link: a GET /logout could be
 * fired by any page (an <img> tag is enough), and signing out must also end the
 * session on the server, not just drop this browser's cookie.
 *
 * If the server cannot be reached the page stays put and the button re-enables,
 * so nobody walks away from a shared device believing they are signed out.
 */
export default function LogoutButton({
  className,
  ariaLabel,
  children,
}: {
  className: string;
  ariaLabel?: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function onClick() {
    if (busy) return;
    setBusy(true);
    try {
      await logout();
    } catch {
      setBusy(false);
      return;
    }
    // Same-origin (production): /login is another page of this app. A separate
    // API origin (local dev) needs a full navigation to that origin.
    if (API_BASE) {
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `${API_BASE}/login`;
    } else {
      router.replace("/login");
    }
  }

  return (
    <button type="button" className={className} aria-label={ariaLabel} onClick={onClick} disabled={busy}>
      {children}
    </button>
  );
}
