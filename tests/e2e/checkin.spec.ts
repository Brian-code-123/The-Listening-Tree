import type { Page } from '@playwright/test';
import { test, expect } from './support/fixtures';
import { query } from '../support/db';

const CHECKIN = /Good (morning|afternoon|evening)/;

async function sendAndWaitForReply(page: Page, text: string) {
  const input = page.locator('input.type_msg');
  await input.fill(text);
  await input.press('Enter');
  await expect(page.locator('.msg_cotainer_send').last()).toContainText(text);
  await expect(page.locator('.msg_cotainer')).toHaveCount(1); // welcome replaced by the real reply
}

async function ageMessages(email: string, hours: number) {
  await query(
    `UPDATE chat_history SET timestamp = timestamp - make_interval(hours => $2)
     WHERE user_id = (SELECT id FROM users WHERE email = $1)`,
    [email, hours],
  );
}

test.describe('Black-box: returning-user check-in', () => {
  test('after a long break the bot opens with a check-in, and only once', async ({ authedPage: page, user }) => {
    await page.goto('/');
    await sendAndWaitForReply(page, 'hello there');
    await ageMessages(user.email, 7);

    await page.reload();
    await expect(page.locator('.msg_cotainer').last()).toContainText(CHECKIN);
    const bubbles = await page.locator('.msg_cotainer, .msg_cotainer_send').count();

    await page.reload();
    await expect(page.locator('.msg_cotainer, .msg_cotainer_send')).toHaveCount(bubbles);
  });

  test('a short break does not trigger a check-in', async ({ authedPage: page, user }) => {
    await page.goto('/');
    await sendAndWaitForReply(page, 'hello there');
    await ageMessages(user.email, 2);

    await page.reload();
    await expect(page.locator('.msg_cotainer').last()).not.toContainText(CHECKIN);
  });

  test('opening an old conversation from the API is read-only: no check-in is added', async ({ authedPage: page, user }) => {
    await page.goto('/');
    await sendAndWaitForReply(page, 'hello there');
    await ageMessages(user.email, 500);
    const api = page.context().request;
    const { conversations } = await (await api.get('/conversations')).json();
    const id = conversations[0].id;
    const { history } = await (await api.get(`/conversations/${id}/messages`)).json();
    expect(history.some((m: { message: string }) => CHECKIN.test(m.message))).toBe(false);
    // ...and it stays that way when loaded again: nothing was written.
    const again = await (await api.get(`/conversations/${id}/messages`)).json();
    expect(again.history).toHaveLength(history.length);
  });

  test('activity in another conversation counts: an old pinned conversation gets no check-in', async ({ authedPage: page }) => {
    const api = page.context().request;
    await api.post('/get_response', { form: { msg: 'first chat' } }); // creates conversation A
    const a = (await (await api.get('/conversations')).json()).conversations[0].id;
    const b = (await (await api.post('/conversations/new')).json()).conversation_id;
    await api.post('/get_response', { form: { msg: 'second chat', conversation_id: String(b) } });
    await api.post(`/conversations/${a}/pin`);
    await query('UPDATE chat_history SET timestamp = timestamp - make_interval(hours => 500) WHERE conversation_id = $1', [a]);

    const { history } = await (await api.get(`/conversations/${a}/messages?checkin=1`)).json();
    expect(history.some((m: { message: string }) => CHECKIN.test(m.message))).toBe(false);
  });

  test('an unanswered check-in does not block the next one after another long break', async ({ authedPage: page, user }) => {
    await page.goto('/');
    await sendAndWaitForReply(page, 'hello there');
    await ageMessages(user.email, 7);
    await page.reload();
    await expect(page.locator('.msg_cotainer').last()).toContainText(CHECKIN);

    await ageMessages(user.email, 9); // the check-in is now 9h old, the user's message 16h old
    await page.reload();
    await expect(page.locator('.msg_cotainer').filter({ hasText: CHECKIN })).toHaveCount(2);
  });
});
