import type { Page } from '@playwright/test';
import { deleteUser, resetRateLimits, seedVerificationCode } from './db';

export { deleteUser };
export type TestUser = { email: string; password: string };
export const E2E_PASSWORD = 'TestPass123!';
const JSON_HEADERS = { Accept: 'application/json' };

export function uniqueEmail(tag = 'user'): string {
  const clean = tag.replace(/[^a-z0-9]/gi, '');
  return `e2e_${clean}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@example.com`;
}

export async function createUser(baseURL: string, tag = 'user'): Promise<TestUser> {
  const email = uniqueEmail(tag);
  await resetRateLimits();
  await seedVerificationCode(email);
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
  const body = await res.json();
  if (!body.success) throw new Error(`createUser failed: ${JSON.stringify(body)}`);
  return { email, password: E2E_PASSWORD };
}

export async function loginViaApi(page: Page, user: TestUser) {
  await resetRateLimits();
  const res = await page.context().request.post('/auth/login', {
    form: { email: user.email, password: user.password, remember_me: 'on' },
    headers: JSON_HEADERS,
  });
  const body = await res.json();
  if (!body.success) throw new Error(`loginViaApi failed: ${JSON.stringify(body)}`);
}
