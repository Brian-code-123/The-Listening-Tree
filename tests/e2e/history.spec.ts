import type { Page } from '@playwright/test';
import { test, expect } from './support/fixtures';
import { setLanguage } from './support/helpers';
import { createUser, deleteUser } from '../support/users';
import { resetRateLimits } from '../support/db';

// Conversations are language-scoped on the backend (GET /conversations and
// POST /conversations/new both filter/insert on the session language), so
// always set the language BEFORE creating conversations for a test.
async function makeConversation(page: Page, title: string): Promise<number> {
  const api = page.context().request;
  const { conversation_id } = await (await api.post('/conversations/new')).json();
  await api.post(`/conversations/${conversation_id}/title`, { form: { title } });
  return conversation_id;
}

test.describe('Black-box: conversation history', () => {
  test('lists conversations by title', async ({ authedPage: page }) => {
    await makeConversation(page, 'Alpha');
    await makeConversation(page, 'Beta');
    await page.goto('/history');
    await expect(page.locator('.conv-card')).toHaveCount(2);
    await expect(page.locator('.conv-title', { hasText: 'Alpha' })).toBeVisible();
  });

  test('pin marks the card and the Pinned filter shows only pinned ones', async ({ authedPage: page }) => {
    await makeConversation(page, 'Alpha');
    await makeConversation(page, 'Beta');
    await page.goto('/history');
    const alpha = page.locator('.conv-card').filter({ hasText: 'Alpha' });
    await alpha.locator('.conv-pin-btn').click();
    await expect(alpha.locator('.conv-pin-btn')).toHaveClass(/pinned/);
    await page.locator('.filter-chip', { hasText: 'Pinned' }).click();
    await expect(page.locator('.conv-card')).toHaveCount(1);
    await expect(page.locator('.conv-title')).toHaveText('Alpha');
  });

  test('rename via the pencil, Enter saves', async ({ authedPage: page }) => {
    await makeConversation(page, 'Old name');
    await page.goto('/history');
    await page.locator('.conv-edit-btn').click();
    const input = page.locator('input.conv-title-input');
    await input.fill('New name');
    await input.press('Enter');
    await expect(page.locator('.conv-title')).toHaveText('New name');
    await page.reload();
    await expect(page.locator('.conv-title')).toHaveText('New name');
  });

  test('delete: cancel keeps it, confirm removes it, and it stays gone after reload', async ({ authedPage: page }) => {
    await makeConversation(page, 'Keep me');
    await makeConversation(page, 'Delete me');
    await page.goto('/history');

    const deleteRequests: string[] = [];
    page.on('request', (r) => {
      if (r.method() === 'DELETE' && r.url().includes('/conversations/')) deleteRequests.push(r.url());
    });

    const target = page.locator('.conv-card').filter({ hasText: 'Delete me' });

    page.once('dialog', (d) => d.dismiss());
    await target.locator('.conv-delete-btn').click();
    await expect(page.locator('.conv-card')).toHaveCount(2);
    expect(deleteRequests).toHaveLength(0);

    page.once('dialog', (d) => d.accept());
    await target.locator('.conv-delete-btn').click();
    await expect(page.locator('.conv-card')).toHaveCount(1);
    expect(deleteRequests).toHaveLength(1);

    await page.reload();
    await expect(page.locator('.conv-card')).toHaveCount(1);
    await expect(page.locator('.conv-title')).toHaveText('Keep me');
  });

  test('deleting the last conversation shows the empty state', async ({ authedPage: page }) => {
    await makeConversation(page, 'Only one');
    await page.goto('/history');
    page.once('dialog', (d) => d.accept());
    await page.locator('.conv-delete-btn').click();
    await expect(page.locator('.empty-state')).toContainText('No conversations yet.');
  });

  test('the delete confirmation is shown in the session language', async ({ authedPage: page }) => {
    await setLanguage(page, 'zh-HK'); // before creating: conversations are language-scoped
    await makeConversation(page, 'Alpha');
    await page.goto('/history');
    let message = '';
    page.once('dialog', async (d) => {
      message = d.message();
      await d.dismiss();
    });
    await page.locator('.conv-delete-btn').click();
    expect(message).toBe('刪除呢個對話？呢個動作無法復原。');
  });

  test("another user cannot delete someone else's conversation (404) and it survives", async ({ authedPage: page, playwright, baseURL }) => {
    const id = await makeConversation(page, 'Private');
    const other = await createUser(baseURL!, 'intruder');
    await resetRateLimits();
    const ctx = await playwright.request.newContext({ baseURL });
    await ctx.post('/auth/login', { form: { email: other.email, password: other.password }, headers: { Accept: 'application/json' } });
    expect((await ctx.delete(`/conversations/${id}`)).status()).toBe(404);
    await ctx.dispose();
    await deleteUser(other.email);

    await page.goto('/history');
    await expect(page.locator('.conv-title', { hasText: 'Private' })).toBeVisible();
  });

  test('a logged-out client gets 401 from DELETE /conversations/{id}', async ({ request }) => {
    expect((await request.delete('/conversations/1')).status()).toBe(401);
  });
});
