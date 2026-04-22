/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant QA
 *     participant Chromium
 *     participant WebKit
 *     participant App as Web App
 *     QA->>Chromium: Open key pages and validate core UI elements
 *     QA->>WebKit: Open key pages and validate core UI elements
 *     Chromium->>App: Request /login and /hk_guide
 *     WebKit->>App: Request /login and /hk_guide
 *     App-->>Chromium: Render compatible layout and controls
 *     App-->>WebKit: Render compatible layout and controls
 */

import { expect, test, type Page } from '@playwright/test';

async function registerAndLogin(page: Page) {
  const suffix = Date.now().toString(36);
  const email = `browser_${suffix}@example.com`;
  const password = 'TestPass123!';

  await page.goto('/register');
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);
  await page.locator('#confirm_password').fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe('Browser test: cross-browser compatibility', () => {
  test('login page renders correctly across browsers', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('form')).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('Hong Kong Local Guide renders tabs and cards across browsers', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/hk_guide');

    await expect(page.locator('.hk-guide-title')).toBeVisible();
    await expect(page.locator('.hk-tab')).toHaveCount(5);

    await page.locator('.hk-tab[data-category="food"]').click();
    await expect(page.locator('#guideContent .hk-guide-card').first()).toBeVisible();
    await expect(page.locator('.hk-card-detail').first()).toBeVisible();
  });

  test('chat page renders core controls and supports basic game command', async ({ page }) => {
    test.setTimeout(60_000);

    await registerAndLogin(page);
    await page.goto('/');

    await expect(page.locator('#messageArea')).toBeVisible();
    await expect(page.locator('#text')).toBeVisible();
    await expect(page.locator('#send')).toBeVisible();
    await expect(page.locator('#micBtn')).toBeVisible();
    await expect(page.locator('#reminderForm')).toBeVisible();
    await expect(page.locator('#guideFab')).toBeVisible();

    const botMessages = page.locator('.msg_cotainer');
    const botCountBefore = await botMessages.count();

    await page.locator('#text').fill('play game');
    await page.locator('#send').click();
    await expect(botMessages).toHaveCount(botCountBefore + 1, { timeout: 30000 });

    await expect(botMessages.last()).toContainText("Let's play");
  });
});
