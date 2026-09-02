/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant User
 *     participant Browser
 *     participant App as FastAPI App
 *     User->>Browser: Register and open chat page
 *     User->>Browser: Tap microphone button
 *     Browser->>Browser: Web Speech API returns transcript
 *     Browser->>App: Auto-submit transcript to /get_response
 *     App-->>Browser: Return bot reply
 *     Browser-->>User: Render transcript and bot response
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

test.describe.serial('Black-box test: voice interaction from user perspective', () => {
  test('user can speak through mic and trigger chat response', async ({ page }, testInfo) => {
    test.setTimeout(60_000);

    const suffix = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    const email = `voice_${suffix}@example.com`;
    const password = 'TestPass123!';
    const transcript = `hello from voice ${suffix}`;

    await page.addInitScript((simulatedTranscript: string) => {
      class MockSpeechRecognition {
        lang = 'en-US';
        interimResults = true;
        continuous = false;
        maxAlternatives = 1;
        private listeners: Record<string, ((event?: any) => void)[]> = {};

        addEventListener(name: string, cb: (event?: any) => void) {
          if (!this.listeners[name]) this.listeners[name] = [];
          this.listeners[name].push(cb);
        }

        private emit(name: string, event?: any) {
          (this.listeners[name] || []).forEach((cb) => cb(event));
        }

        start() {
          setTimeout(() => {
            const alt = { transcript: simulatedTranscript };
            const result: any = [alt];
            result.isFinal = true;
            const event = { resultIndex: 0, results: [result] };
            this.emit('result', event);
            this.emit('end');
          }, 100);
        }

        stop() {
          this.emit('end');
        }
      }

      (window as any).SpeechRecognition = MockSpeechRecognition;
      (window as any).webkitSpeechRecognition = undefined;
    }, transcript);

    await test.step('Register and open chat page', async () => {
      await page.goto('/register');
      await page.locator('#email').fill(email);
      await page.locator('#password').fill(password);
      await page.locator('#confirm_password').fill(password);
      await page.locator('button[type="submit"]').click();

      await expect(page).toHaveURL(/\/$/);
      await expect(page.locator('#micBtn')).toBeVisible();
      await captureStep(page, testInfo, '01-register-voice');
    });

    await test.step('Tap mic to auto-transcribe and auto-send', async () => {
      const userMessages = page.locator('.msg_cotainer_send');
      const botMessages = page.locator('.msg_cotainer');
      const userCountBefore = await userMessages.count();
      const botCountBefore = await botMessages.count();

      await page.locator('#micBtn').click();
      await expect(userMessages).toHaveCount(userCountBefore + 1, { timeout: 20000 });
      await expect(botMessages).toHaveCount(botCountBefore + 1, { timeout: 20000 });

      await expect(userMessages.last()).toContainText(transcript);
      await expect(botMessages.last()).not.toHaveText('');
      await captureStep(page, testInfo, '02-voice-transcript-sent');
    });

    await test.step('Verify voice transcript is persisted', async () => {
      const historyResponse = await page.request.get('/get_chat_history');
      expect(historyResponse.ok()).toBeTruthy();

      const payload = await historyResponse.json();
      expect(payload.history).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ sender: 'user', message: transcript }),
          expect.objectContaining({ sender: 'bot' }),
        ]),
      );

      await captureStep(page, testInfo, '03-voice-history');
    });
  });
});
