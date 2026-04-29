/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant User
 *     participant Browser
 *     participant App as FastAPI App
 *     User->>Browser: Register and open chat page
 *     User->>Browser: Send free-form AI message
 *     Browser->>App: POST /get_response
 *     App-->>Browser: Return AI response
 *     Browser-->>User: Render user and bot messages
 */

import { expect, test, type Page, type TestInfo } from '@playwright/test';

async function captureStep(page: Page, testInfo: TestInfo, name: string) {
  const screenshotPath = testInfo.outputPath(`${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(name, {
    path: screenshotPath,
    contentType: 'image/png',
  });
}

test.describe.serial('Black-box test: AI chat from user perspective', () => {
  test('user can send a chat message and receive AI reply', async ({ page }, testInfo) => {
    const suffix = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    const email = `ai_chat_${suffix}@example.com`;
    const password = 'TestPass123!';
    const prompt = `How are you today? ${suffix}`;

    await test.step('Register and open chat page', async () => {
      await page.goto('/register');
      await page.locator('#email').fill(email);
      await page.locator('#password').fill(password);
      await page.locator('#confirm_password').fill(password);
      await page.locator('button[type="submit"]').click();

      await expect(page).toHaveURL(/\/$/);
      await expect(page.locator('#messageArea')).toBeVisible();
      await captureStep(page, testInfo, '01-register-chat');
    });

    await test.step('Send user message and wait for AI response', async () => {
      const userMessages = page.locator('.msg_cotainer_send');
      const botMessages = page.locator('.msg_cotainer');
      const userCountBefore = await userMessages.count();
      const botCountBefore = await botMessages.count();

      await page.locator('#text').fill(prompt);
      await page.locator('#send').click();
      await expect(userMessages).toHaveCount(userCountBefore + 1, { timeout: 20000 });
      await expect(botMessages).toHaveCount(botCountBefore + 1, { timeout: 20000 });

      await expect(userMessages.last()).toContainText(prompt);
      await expect(botMessages.last()).not.toHaveText('');
      await captureStep(page, testInfo, '02-chat-response');
    });

    await test.step('Verify conversation persisted in API history', async () => {
      const historyResponse = await page.request.get('/get_chat_history');
      expect(historyResponse.ok()).toBeTruthy();

      const payload = await historyResponse.json();
      expect(payload.history).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ sender: 'user', message: prompt }),
          expect.objectContaining({ sender: 'bot' }),
        ]),
      );

      await captureStep(page, testInfo, '03-chat-history');
    });
  });
});
