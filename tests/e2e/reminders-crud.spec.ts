/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant Tester
 *     participant Browser
 *     participant FastAPI
 *     participant DB
 *     Tester->>Browser: register user and open chat
 *     Browser->>FastAPI: create reminder
 *     FastAPI->>DB: insert/select/update/delete reminder rows
 *     Browser-->>Tester: screenshots and CRUD assertions
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

test.describe.serial('Reminder CRUD lifecycle', () => {
  test('creates, reads, updates, and deletes a reminder', async ({ page }, testInfo) => {
    const suffix = Date.now().toString(36);
    const email = `e2e_${suffix}@example.com`;
    const password = 'TestPass123!';
    const label = `take medicine ${suffix}`;
    const time = '09:30';

    await test.step('Register and log in', async () => {
      await page.goto('/register');
      await page.locator('#email').fill(email);
      await page.locator('#password').fill(password);
      await page.locator('#confirm_password').fill(password);
      await page.locator('button[type="submit"]').click();

      await expect(page).toHaveURL(/\/$/);
      await expect(page.locator('#reminderForm')).toBeVisible();
      await captureStep(page, testInfo, '01-register');
    });

    await test.step('Create reminder through the UI', async () => {
      await page.locator('#reminderLabel').fill(label);
      await page.locator('#reminderTime').fill(time);
      await page.locator('#reminderForm button[type="submit"]').click();

      await expect(page.locator('#reminderList')).toContainText(label);
      await captureStep(page, testInfo, '02-create');
    });

    await test.step('Read reminder from API and page', async () => {
      const response = await page.request.get('/get_reminders');
      expect(response.ok()).toBeTruthy();

      const payload = await response.json();
      expect(payload.reminders).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ label, time, active: true }),
        ]),
      );

      await page.reload();
      await expect(page.locator('#reminderList')).toContainText(label);
      await captureStep(page, testInfo, '03-read');
    });

    await test.step('Update reminder by deactivating it', async () => {
      const updateResponse = await page.request.post('/deactivate_reminder', {
        form: { label },
      });
      expect(updateResponse.ok()).toBeTruthy();

      await page.reload();
      await expect(page.locator('#reminderList')).toContainText(label);
      await expect(page.locator('#reminderList .reminder-item.inactive')).toContainText(label);
      await captureStep(page, testInfo, '04-update');
    });

    await test.step('Delete reminder via chat command', async () => {
      const responsePromise = page.waitForResponse((response) => {
        return response.url().includes('/get_response') && response.request().method() === 'POST';
      });

      await page.locator('#text').fill(`delete reminder ${label}`);
      await page.locator('#send').click();
      await responsePromise;

      await page.reload();
      await expect(page.locator('#reminderList')).not.toContainText(label);
      await captureStep(page, testInfo, '05-delete');
    });
  });
});