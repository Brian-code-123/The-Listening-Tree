/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant User
 *     participant Browser
 *     participant App as FastAPI App
 *     User->>Browser: Register and open chat page
 *     User->>Browser: Send "play game"
 *     Browser->>App: POST /get_response
 *     App-->>Browser: Return first quiz question
 *     User->>Browser: Send "answer paris" and "exit game"
 *     App-->>Browser: Return score updates and exit message
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

async function sendMessage(page: Page, message: string) {
  const responsePromise = page.waitForResponse((response) => {
    return response.url().includes('/get_response') && response.request().method() === 'POST';
  });

  await page.locator('#text').fill(message);
  await page.locator('#send').click();
  await responsePromise;
}

test.describe.serial('Black-box test: cognitive game from user perspective', () => {
  test('user can start game, answer question, and exit game', async ({ page }, testInfo) => {
    test.setTimeout(60_000);

    const suffix = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    const email = `game_${suffix}@example.com`;
    const password = 'TestPass123!';

    await test.step('Register and open chat page', async () => {
      await page.goto('/register');
      await page.locator('#email').fill(email);
      await page.locator('#password').fill(password);
      await page.locator('#confirm_password').fill(password);
      await page.locator('button[type="submit"]').click();

      await expect(page).toHaveURL(/\/$/);
      await expect(page.locator('#messageArea')).toBeVisible();
      await captureStep(page, testInfo, '01-register-game');
    });

    await test.step('Start cognitive game', async () => {
      await sendMessage(page, 'play game');
      await expect(page.locator('.msg_cotainer').last()).toContainText("Let's play");
      await expect(page.locator('.msg_cotainer').last()).toContainText('First question');
      await captureStep(page, testInfo, '02-game-start');
    });

    await test.step('Answer question and verify score progression', async () => {
      await sendMessage(page, 'answer paris');
      await expect(page.locator('.msg_cotainer').last()).toContainText('Correct! Score: 1');
      await expect(page.locator('.msg_cotainer').last()).toContainText('Next question');
      await captureStep(page, testInfo, '03-game-answer');
    });

    await test.step('Exit game and confirm stop response', async () => {
      await sendMessage(page, 'exit game');
      await expect(page.locator('.msg_cotainer').last()).toContainText('Game stopped');
      await captureStep(page, testInfo, '04-game-exit');
    });
  });
});
