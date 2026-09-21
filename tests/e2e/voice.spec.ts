import { test, expect } from './support/fixtures';
import { setLanguage } from './support/helpers';

test.skip(({ browserName }) => browserName !== 'chromium', 'Web Speech API is only exercised on Chromium');

test.describe('Black-box: voice input', () => {
  test('tapping the mic fills the message box with the recognised speech', async ({ authedPage: page }) => {
    const transcript = 'hello from the microphone';
    await page.addInitScript((spoken: string) => {
      class MockSpeechRecognition {
        lang = 'en-US';
        interimResults = true;
        continuous = false;
        maxAlternatives = 1;
        private listeners: Record<string, ((e?: unknown) => void)[]> = {};
        addEventListener(name: string, cb: (e?: unknown) => void) {
          (this.listeners[name] ||= []).push(cb);
        }
        private emit(name: string, e?: unknown) {
          (this.listeners[name] || []).forEach((cb) => cb(e));
        }
        start() {
          setTimeout(() => {
            const result: any = [{ transcript: spoken }];
            result.isFinal = true;
            this.emit('result', { resultIndex: 0, results: [result] });
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

    await page.goto('/');
    await page.locator('button.mic-btn[title="Start Voice"]').click();
    await expect(page.locator('input.type_msg')).toHaveValue(transcript);
    await page.locator('button.send_btn[type="submit"]').click();
    await expect(page.locator('.msg_cotainer_send').last()).toContainText(transcript);
  });

  test('the mic tooltip is localized', async ({ authedPage: page }) => {
    await setLanguage(page, 'zh-HK');
    await page.goto('/');
    await expect(page.locator('button.mic-btn').first()).toHaveAttribute('title', '開始語音');
  });
});
