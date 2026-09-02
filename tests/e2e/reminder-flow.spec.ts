/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant User
 *     participant Browser
 *     participant App as FastAPI App
 *     User->>Browser: Register with email/password
 *     Browser->>App: Submit registration form
 *     App-->>Browser: Redirect to chat page
 *     User->>Browser: Add reminder from reminder form
 *     Browser->>App: Send reminder command
 *     App-->>Browser: Render reminder in list
 *     User->>Browser: Delete reminder from list
 *     Browser->>App: Send delete reminder command
 *     App-->>Browser: Reminder removed from UI
 */

import { expect, test } from '@playwright/test';

test.describe('Black-box test: reminder feature from user perspective', () => {
  test('user can register, create and delete a reminder through UI behavior', async ({ page }) => {
    const suffix = Date.now().toString(36);
    const email = `blackbox_${suffix}@example.com`;
    const password = 'TestPass123!';
    const label = `walk ${suffix}`;
    const time = '08:45';

    await page.goto('/register');
    await page.locator('#email').fill(email);
    await page.locator('#password').fill(password);
    await page.locator('#confirm_password').fill(password);
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('#reminderForm')).toBeVisible();

    await page.locator('#reminderLabel').fill(label);
    await page.locator('#reminderTime').fill(time);

    const createResponsePromise = page.waitForResponse((response) => {
      return response.url().includes('/get_response') && response.request().method() === 'POST';
    });
    await page.locator('#reminderForm button[type="submit"]').click();
    await createResponsePromise;

    const createdReminder = page.locator(`.reminder-item:has(.reminder-label:has-text("${label}"))`);
    await expect(createdReminder).toBeVisible({ timeout: 15000 });
    await expect(createdReminder).toContainText(time);

    await page.locator(`.delete-reminder[data-label="${label}"]`).click();

    await expect(page.locator('#reminderList')).not.toContainText(label, { timeout: 10000 });
  });
});
