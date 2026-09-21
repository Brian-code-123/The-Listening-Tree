import { test, expect } from './support/fixtures';

test.describe('Black-box: accessibility mode', () => {
  test('exposes landmarks and a skip link', async ({ authedPage: page }) => {
    await page.goto('/accessibility');
    await expect(page.locator('a.skip-link')).toHaveAttribute('href', '#main-content');
    await expect(page.locator('main#main-content')).toBeVisible();
    await expect(page.locator('[role="log"][aria-label="Chat messages"]')).toBeVisible();
  });

  test('a message can be sent and gets a reply', async ({ authedPage: page }) => {
    await page.goto('/accessibility');
    await page.locator('#messageInput').fill('hello accessibility');
    await page.locator('button[aria-label="Send message"]').click();
    await expect(page.locator('.message-user').last()).toContainText('hello accessibility');
    await expect(page.locator('.message-bot').last()).not.toHaveText(/^\s*$/);
  });

  test('clear empties the conversation', async ({ authedPage: page }) => {
    await page.goto('/accessibility');
    await page.locator('#messageInput').fill('to be cleared');
    await page.locator('#messageInput').press('Enter');
    await expect(page.locator('.message-user').last()).toContainText('to be cleared');
    await page.locator('button[aria-label="Clear all messages"]').click();
    await expect(page.locator('.message-user')).toHaveCount(0);
  });
});
