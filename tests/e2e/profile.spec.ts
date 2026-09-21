import { test, expect } from './support/fixtures';
import { resetRateLimits } from '../support/db';
import { E2E_PASSWORD } from '../support/users';

test.describe('Black-box: profile', () => {
  test('the display name can be changed and persists', async ({ authedPage: page }) => {
    await page.goto('/profile');
    await page.locator('#display_name').fill('Grandma Lee');
    await page.locator('form').first().locator('button[type="submit"]').click();
    await expect(page.locator('.form-status.success').first()).toBeVisible();
    await page.reload();
    await expect(page.locator('#display_name')).toHaveValue('Grandma Lee');
  });

  test('a wrong current password is rejected with a field error', async ({ authedPage: page }) => {
    await page.goto('/profile');
    await page.locator('#current_password').fill('NotMyPassword1!');
    await page.locator('#new_password').fill('BrandNew456!');
    await page.locator('#confirm_new_password').fill('BrandNew456!');
    await page.locator('form').nth(1).locator('button[type="submit"]').click();
    await expect(
      page.locator('.mb-3', { has: page.locator('#current_password') }).locator('.field-error'),
    ).toHaveText(/.+/);
  });

  test('changing the password lets the user log in with the new one', async ({ authedPage: page, user, playwright, baseURL }) => {
    await page.goto('/profile');
    await page.locator('#current_password').fill(E2E_PASSWORD);
    await page.locator('#new_password').fill('BrandNew456!');
    await page.locator('#confirm_new_password').fill('BrandNew456!');
    await page.locator('form').nth(1).locator('button[type="submit"]').click();
    await expect(page.locator('.form-status.success').last()).toBeVisible();

    await resetRateLimits();
    const ctx = await playwright.request.newContext({ baseURL });
    const res = await ctx.post('/auth/login', {
      form: { email: user.email, password: 'BrandNew456!' },
      headers: { Accept: 'application/json' },
    });
    expect((await res.json()).success).toBe(true);
    await ctx.dispose();
  });
});
