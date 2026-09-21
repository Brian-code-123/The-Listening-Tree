import type { Page } from '@playwright/test';
import { test, expect } from './support/fixtures';
import { openSidebarIfMobile } from './support/helpers';

async function send(page: Page, text: string) {
  const input = page.locator('input.type_msg');
  await input.fill(text);
  await input.press('Enter');
}

// Only valid for the FIRST message of a fresh conversation: the welcome bubble
// is replaced by the user's bubble (bot count 0) and then by the real reply
// (bot count 1). Waiting on the user bubble first avoids matching the welcome
// bubble's count of 1 before React has re-rendered.
async function sendFirstMessageAndWaitForReply(page: Page, text: string) {
  await send(page, text);
  await expect(page.locator('.msg_cotainer_send').last()).toContainText(text);
  await expect(page.locator('.msg_cotainer')).toHaveCount(1);
}

test.describe('Black-box: chat', () => {
  test('sending a message shows it and produces a bot reply', async ({ authedPage: page }) => {
    await page.goto('/');
    await expect(page.locator('.msg_cotainer')).toHaveCount(1); // welcome bubble
    await send(page, 'hello there');
    await expect(page.locator('.msg_cotainer_send').last()).toContainText('hello there');
    await expect(page.locator('.msg_cotainer')).toHaveCount(1); // welcome replaced by the real reply
    await expect(page.locator('.msg_cotainer').last()).not.toHaveText(/^\s*$/);
  });

  test('the send button also submits', async ({ authedPage: page }) => {
    await page.goto('/');
    await page.locator('input.type_msg').fill('via button');
    await page.locator('button.send_btn[type="submit"]').click();
    await expect(page.locator('.msg_cotainer_send').last()).toContainText('via button');
  });

  test('the conversation survives a reload', async ({ authedPage: page }) => {
    await page.goto('/');
    await sendFirstMessageAndWaitForReply(page, 'remember me please');
    await page.reload();
    await expect(page.locator('.msg_cotainer_send').last()).toContainText('remember me please');
  });

  test('"new conversation" starts an empty chat', async ({ authedPage: page }) => {
    await page.goto('/');
    await sendFirstMessageAndWaitForReply(page, 'first thread');
    await openSidebarIfMobile(page);
    await page.locator('button[title="New conversation"]').click();
    await expect(page.locator('.msg_cotainer_send')).toHaveCount(0);
  });

  test('cognitive game: start, answer, exit', async ({ authedPage: page }) => {
    await page.goto('/');
    await send(page, 'play game');
    await expect(page.locator('.msg_cotainer').last()).toContainText("Let's play");
    await expect(page.locator('.msg_cotainer').last()).toContainText('First question');
    await send(page, 'answer paris');
    await expect(page.locator('.msg_cotainer').last()).toContainText('Correct! Score: 1');
    await expect(page.locator('.msg_cotainer').last()).toContainText('Next question');
    await send(page, 'exit game');
    await expect(page.locator('.msg_cotainer').last()).toContainText('Game stopped');
  });

  test('the theme toggle switches to dark and persists across reloads', async ({ authedPage: page }) => {
    await page.goto('/');
    await page.locator('#themeToggle').click();
    await expect(page.locator('.page-chat')).toHaveAttribute('data-theme', 'dark');
    await page.reload();
    await expect(page.locator('.page-chat')).toHaveAttribute('data-theme', 'dark');
  });
});
