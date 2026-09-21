import type { Page } from '@playwright/test';
import { test, expect } from './support/fixtures';
import { openSidebarIfMobile } from './support/helpers';

const XSS = `<img src=x onerror="window.__xss=1"><script>window.__xss=1</script>`;

async function send(page: Page, text: string) {
  const input = page.locator('input.type_msg');
  await input.fill(text);
  await input.press('Enter');
}

async function expectNoInjection(page: Page, dialogs: string[]) {
  expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();
  await expect(page.locator('img[src="x"]')).toHaveCount(0);
  expect(dialogs).toEqual([]);
}

test.describe('Edge cases: injection and odd input', () => {
  test('HTML in a chat message is shown as text, never executed', async ({ authedPage: page }) => {
    const dialogs: string[] = [];
    page.on('dialog', async (d) => {
      dialogs.push(d.message());
      await d.dismiss();
    });
    await page.goto('/');
    await send(page, XSS);
    await expect(page.locator('.msg_cotainer_send').last()).toContainText('<img src=x');
    await expect(page.locator('.msg_cotainer')).toHaveCount(1); // the reply arrived too
    await expectNoInjection(page, dialogs);
  });

  test('HTML in a reminder label is shown as text, never executed', async ({ authedPage: page }) => {
    const dialogs: string[] = [];
    page.on('dialog', async (d) => {
      dialogs.push(d.message());
      await d.dismiss();
    });
    await page.goto('/');
    await openSidebarIfMobile(page);
    await page.locator('#reminderLabel').fill(XSS);
    await page.locator('#reminderTime').fill('09:30');
    await page.getByRole('button', { name: 'Add reminder' }).click();
    await expect(page.locator('.reminder-label').filter({ hasText: '<img src=x' })).toBeVisible();
    await expectNoInjection(page, dialogs);
  });

  test('HTML in a conversation title is shown as text, never executed', async ({ authedPage: page }) => {
    const dialogs: string[] = [];
    page.on('dialog', async (d) => {
      dialogs.push(d.message());
      await d.dismiss();
    });
    const api = page.context().request;
    const { conversation_id } = await (await api.post('/conversations/new')).json();
    await api.post(`/conversations/${conversation_id}/title`, { form: { title: XSS } });
    await page.goto('/history');
    await expect(page.locator('.conv-title')).toContainText('<img src=x');
    await expectNoInjection(page, dialogs);
  });

  test('a whitespace-only message is not sent', async ({ authedPage: page }) => {
    await page.goto('/');
    await send(page, '     ');
    await page.waitForTimeout(500);
    await expect(page.locator('.msg_cotainer_send')).toHaveCount(0);
  });

  test('a Chinese and emoji reminder label round-trips intact', async ({ authedPage: page }) => {
    const label = '食藥 💊 同 飲水 🥤';
    const api = page.context().request;
    const created = await api.post('/reminders', { form: { label, time: '08:15' } });
    expect(created.ok()).toBeTruthy();
    await page.goto('/');
    await openSidebarIfMobile(page);
    await expect(page.locator('.reminder-label', { hasText: label })).toBeVisible();
  });
});

test.describe('Edge cases: sessions and conversations changing under the user', () => {
  test('sending after the session has expired shows an error bubble, not a broken page', async ({ authedPage: page }) => {
    await page.goto('/');
    await expect(page.locator('input.type_msg')).toBeVisible();
    await page.context().clearCookies(); // the session expires while the page is open
    await send(page, 'anyone there?');
    await expect(page.locator('.msg_cotainer').last()).toContainText(/something went wrong/i);
    await expect(page.locator('input.type_msg')).toBeVisible();
  });

  test('opening a conversation that was deleted elsewhere still leaves a working chat', async ({ authedPage: page }) => {
    const api = page.context().request;
    const { conversation_id } = await (await api.post('/conversations/new')).json();
    await api.post('/get_response', { form: { msg: 'hello', conversation_id: String(conversation_id) } });
    expect((await api.delete(`/conversations/${conversation_id}`)).ok()).toBeTruthy();

    await page.goto(`/?conversation_id=${conversation_id}`);
    await expect(page.locator('input.type_msg')).toBeVisible();
    await send(page, 'still works');
    await expect(page.locator('.msg_cotainer_send').last()).toContainText('still works');
    await expect(page.locator('.msg_cotainer').last()).not.toHaveText(/^\s*$/);
  });

  test('deleting a conversation while its title is being edited removes it cleanly', async ({ authedPage: page }) => {
    const api = page.context().request;
    const { conversation_id } = await (await api.post('/conversations/new')).json();
    await api.post(`/conversations/${conversation_id}/title`, { form: { title: 'Editing' } });
    await page.goto('/history');
    await page.locator('.conv-edit-btn').click();
    await expect(page.locator('input.conv-title-input')).toBeVisible();

    page.once('dialog', (d) => d.accept());
    await page.locator('.conv-delete-btn').click();
    await expect(page.locator('.conv-card')).toHaveCount(0);
    await expect(page.locator('.empty-state')).toBeVisible();
  });
});
