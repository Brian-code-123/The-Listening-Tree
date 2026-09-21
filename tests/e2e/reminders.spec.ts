import { test, expect } from './support/fixtures';
import { openSidebarIfMobile, setLanguage } from './support/helpers';
import { resetRateLimits } from '../support/db';
import { createUser, deleteUser } from '../support/users';

test.describe('Black-box: reminders (UI)', () => {
  test('a user can add and delete a reminder from the sidebar', async ({ authedPage: page }) => {
    await page.goto('/');
    await openSidebarIfMobile(page);
    await page.locator('#reminderLabel').fill('Take medicine');
    await page.locator('#reminderTime').fill('09:30');
    await page.getByRole('button', { name: 'Add reminder' }).click();

    const item = page.locator('.reminder-card .reminder-item').filter({ hasText: 'Take medicine' });
    await expect(item).toBeVisible();
    await expect(item).toContainText('09:30');

    await item.locator('.reminder-delete').click();
    await expect(item).toHaveCount(0);
  });

  test('the add-form stays aligned: label full width, compact time input beside the button', async ({ authedPage: page, isMobile }) => {
    test.skip(isMobile, 'the sidebar layout being measured only exists at desktop widths');
    await page.goto('/');
    const label = await page.locator('#reminderLabel').boundingBox();
    const time = await page.locator('#reminderTime').boundingBox();
    const button = await page.getByRole('button', { name: 'Add reminder' }).boundingBox();
    expect(label && time && button).toBeTruthy();
    expect(time!.width).toBeLessThanOrEqual(131); // max-width: 130px
    expect(label!.width).toBeGreaterThan(time!.width);
    expect(button!.x).toBeGreaterThan(time!.x + time!.width - 1); // button sits to the right
    expect(Math.abs(button!.y - time!.y)).toBeLessThan(24); // same row
  });

  test('preset suggestions follow the session language', async ({ authedPage: page }) => {
    await setLanguage(page, 'zh-HK');
    await page.goto('/');
    await expect(page.locator('#reminderPresets option').first()).toHaveAttribute('value', '食藥');
  });
});

test.describe('Black-box: reminders (API contract)', () => {
  test('create, list, delete, and delete-again returns 404', async ({ authedPage: page }) => {
    const api = page.context().request;
    const created = await api.post('/reminders', { form: { label: 'Walk', time: '07:15' } });
    expect(created.ok()).toBeTruthy();
    const { id } = await created.json();

    const list = await (await api.get('/get_reminders')).json();
    expect(list.reminders.some((r: { id: number; label: string; time: string }) => r.id === id && r.label === 'Walk' && r.time === '07:15')).toBe(true);

    expect((await api.delete(`/reminders/${id}`)).ok()).toBeTruthy();
    expect((await api.delete(`/reminders/${id}`)).status()).toBe(404);
  });

  test('invalid time and empty label are rejected with 400', async ({ authedPage: page }) => {
    const api = page.context().request;
    expect((await api.post('/reminders', { form: { label: 'Bad', time: '25:99' } })).status()).toBe(400);
    expect((await api.post('/reminders', { form: { label: '   ', time: '09:00' } })).status()).toBe(400);
  });

  test('a logged-out client cannot create reminders (401)', async ({ request }) => {
    expect((await request.post('/reminders', { form: { label: 'x', time: '09:00' } })).status()).toBe(401);
  });

  test("one user cannot delete another user's reminder", async ({ authedPage: page, playwright, baseURL }) => {
    const created = await page.context().request.post('/reminders', { form: { label: 'Mine', time: '10:00' } });
    const { id } = await created.json();

    const other = await createUser(baseURL!, 'other');
    await resetRateLimits();
    const ctx = await playwright.request.newContext({ baseURL });
    await ctx.post('/auth/login', { form: { email: other.email, password: other.password }, headers: { Accept: 'application/json' } });
    expect((await ctx.delete(`/reminders/${id}`)).status()).toBe(404);
    await ctx.dispose();
    await deleteUser(other.email);
  });
});
