import { API_BASE } from "./api";

interface JsonResult {
  success: boolean;
  message?: string;
  field?: string;
  redirect?: string;
}

async function postForm(path: string, fields: Record<string, string>): Promise<{ status: number; body: JsonResult }> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body: new URLSearchParams(fields),
  });
  const body = (await res.json()) as JsonResult;
  // The backend returns a bare path ("/") since it has no notion of
  // API_BASE. In production that's same-origin and fine as-is, but
  // locally this app and the backend are two different dev-server
  // origins (3001 vs 5000) — a bare "/" would navigate within *this*
  // app's origin instead of back to the FastAPI-served page. Prefixing
  // with API_BASE here means every caller (login, register, ...) gets
  // the right target without having to remember this themselves.
  if (body.redirect) {
    body.redirect = `${API_BASE}${body.redirect}`;
  }
  return { status: res.status, body };
}

// Posts go to /auth/login/-register, not /login//register: those page paths
// are rewritten to this app in production, and a rewrite covers every method,
// so posting to the page path returns 405 from the static page instead of
// reaching the backend.
export function login(email: string, password: string, rememberMe: boolean) {
  return postForm("/auth/login", {
    email,
    password,
    ...(rememberMe ? { remember_me: "on" } : {}),
  });
}

export function register(email: string, password: string, confirmPassword: string, verificationCode: string) {
  return postForm("/auth/register", {
    email,
    password,
    confirm_password: confirmPassword,
    verification_code: verificationCode,
  });
}

export async function sendVerificationCode(email: string): Promise<{ status: number; body: { success: boolean; message: string } }> {
  const res = await fetch(`${API_BASE}/send_verification_code`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const body = await res.json();
  return { status: res.status, body };
}

export function updateDisplayName(displayName: string) {
  return postForm("/profile/name", { display_name: displayName });
}

export function updatePassword(currentPassword: string, newPassword: string, confirmNewPassword: string) {
  return postForm("/profile/password", {
    current_password: currentPassword,
    new_password: newPassword,
    confirm_new_password: confirmNewPassword,
  });
}
