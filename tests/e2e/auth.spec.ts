import { test, expect } from './support/fixtures';
import { clearRateLimitKey, rateLimitCount, resetRateLimits, seedVerificationCode } from '../support/db';
import { deleteUser, uniqueEmail, E2E_PASSWORD } from '../support/users';

const SUBMIT = 'form.auth-form button[type="submit"]';

test.describe('Black-box: authentication', () => {
  test('a visitor can register with an emailed code and lands on the chat page', async ({ page }) => {
    const email = uniqueEmail('reg');
    await resetRateLimits();
    await seedVerificationCode(email, '123456');
    try {
      await page.goto('/register');
      await page.locator('#email').fill(email);
      await page.locator('#password').fill(E2E_PASSWORD);
      await page.locator('#confirm_password').fill(E2E_PASSWORD);
      await page.locator('#verification_code').fill('123456');
      await page.locator(SUBMIT).click();
      await expect(page).toHaveURL(/\/$/);
      await expect(page.locator('input.type_msg')).toBeVisible();
    } finally {
      await deleteUser(email);
    }
  });

  test('registering with a wrong verification code is rejected', async ({ page }) => {
    await resetRateLimits();
    await page.goto('/register');
    await page.locator('#email').fill(uniqueEmail('badcode'));
    await page.locator('#password').fill(E2E_PASSWORD);
    await page.locator('#confirm_password').fill(E2E_PASSWORD);
    await page.locator('#verification_code').fill('000000');
    await page.locator(SUBMIT).click();
    await expect(page.locator('.field-error').filter({ hasText: /incorrect|expired/i })).toBeVisible();
    await expect(page).toHaveURL(/\/register$/);
  });

  test('mismatched confirm-password shows the no-match indicator', async ({ page }) => {
    await page.goto('/register');
    await page.locator('#password').fill(E2E_PASSWORD);
    await page.locator('#confirm_password').fill('Different123!');
    await expect(page.locator('.password-match.no-match')).toBeVisible();
    await page.locator('#confirm_password').fill(E2E_PASSWORD);
    await expect(page.locator('.password-match.match')).toBeVisible();
  });

  test('an existing user can log in and reach the chat page', async ({ page, user }) => {
    await page.goto('/login');
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill(user.password);
    await page.locator(SUBMIT).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('input.type_msg')).toBeVisible();
  });

  test('a wrong password shows an error and stays on the login page', async ({ page, user }) => {
    await page.goto('/login');
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill('WrongPass999!');
    await page.locator(SUBMIT).click();
    await expect(page.locator('.alert-danger')).toContainText('Invalid email or password');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('the show/hide password button toggles the field type and its label', async ({ page }) => {
    await page.goto('/login');
    const field = page.locator('#password');
    await expect(field).toHaveAttribute('type', 'password');
    await page.locator('button[aria-label="Show password"]').click();
    await expect(field).toHaveAttribute('type', 'text');
    await expect(page.locator('button[aria-label="Hide password"]')).toBeVisible();
  });

  test('logging out returns to the login page', async ({ authedPage: page }) => {
    await page.goto('/');
    await page.locator('a[href$="/logout"]').first().click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('visiting a protected page while logged out redirects to login', async ({ page }) => {
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('login is rate limited after too many attempts (429)', async ({ request }) => {
    // The limiter keys on the first X-Forwarded-For entry. A private address from
    // the reserved TEST-NET-3 range gives this test its own counter, which the
    // shared resetRateLimits() (run by parallel workers) deliberately leaves alone.
    const ip = `203.0.113.${1 + Math.floor(Math.random() * 250)}`;
    const key = `login:${ip}`;
    try {
      const statuses: number[] = [];
      for (let i = 0; i < 12; i++) {
        const res = await request.post('/auth/login', {
          form: { email: 'nobody@example.com', password: 'x' },
          headers: { Accept: 'application/json', 'X-Forwarded-For': ip },
        });
        statuses.push(res.status());
      }
      expect(await rateLimitCount(key)).toBe(12); // proves the header reached the limiter
      expect(statuses.slice(0, 10)).not.toContain(429);
      expect(statuses.slice(10)).toEqual([429, 429]);
    } finally {
      await clearRateLimitKey(key);
    }
  });
});
