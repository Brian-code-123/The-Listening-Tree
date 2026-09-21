import { test, expect } from './support/fixtures';

test.describe('E2E stack smoke', () => {
  test('backend health is reachable through the Next origin', async ({ request }) => {
    const res = await request.get('/health');
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).ok).toBe(true);
  });

  test('login stays on the Next origin (same-origin, like production)', async ({ page, user, baseURL }) => {
    await page.goto('/login');
    await page.locator('#email').fill(user.email);
    await page.locator('#password').fill(user.password);
    await page.locator('form.auth-form button[type="submit"]').click();
    await expect(page).toHaveURL(new RegExp(`^${new URL(baseURL!).origin}/$`));
    await expect(page.locator('input.type_msg')).toBeVisible();
  });
});
