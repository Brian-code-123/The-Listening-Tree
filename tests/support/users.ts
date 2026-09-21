import type { Page } from '@playwright/test';
import { deleteUser, resetRateLimits, seedVerificationCode } from './db';

export { deleteUser };
export type TestUser = { email: string; password: string };
export const E2E_PASSWORD = 'TestPass123!';
const JSON_HEADERS = { Accept: 'application/json' };

// The Next proxy reuses keep-alive sockets that uvicorn may have just closed,
// which surfaces as "socket hang up" / ECONNRESET. Retry only thrown network
// errors — never an application-level { success: false } answer.
async function withRetry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      last = err;
      await new Promise((r) => setTimeout(r, 300 * (i + 1)));
    }
  }
  throw last;
}

export function uniqueEmail(tag = 'user'): string {
  const clean = tag.replace(/[^a-z0-9]/gi, '');
  return `e2e_${clean}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@example.com`;
}

export async function createUser(baseURL: string, tag = 'user'): Promise<TestUser> {
  const email = uniqueEmail(tag);
  await resetRateLimits();
  await seedVerificationCode(email);
  const body = await withRetry(async () => {
    const res = await fetch(`${baseURL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', ...JSON_HEADERS },
      body: new URLSearchParams({
        email,
        password: E2E_PASSWORD,
        confirm_password: E2E_PASSWORD,
        verification_code: '123456',
      }),
    });
    return res.json();
  });
  if (!body.success) throw new Error(`createUser failed: ${JSON.stringify(body)}`);
  return { email, password: E2E_PASSWORD };
}

export async function loginViaApi(page: Page, user: TestUser) {
  await resetRateLimits();
  const body = await withRetry(async () => {
    const res = await page.context().request.post('/auth/login', {
      form: { email: user.email, password: user.password, remember_me: 'on' },
      headers: JSON_HEADERS,
    });
    return res.json();
  });
  if (!body.success) throw new Error(`loginViaApi failed: ${JSON.stringify(body)}`);
}
