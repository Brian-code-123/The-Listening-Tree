import { test, expect } from './support/fixtures';

const AUTHED_PAGES: { path: string; landmark: string }[] = [
  { path: '/', landmark: 'input.type_msg' },
  { path: '/history', landmark: '.hk-guide-title' },
  { path: '/profile', landmark: '.profile-card' },
  { path: '/accessibility', landmark: '#messageInput' },
  { path: '/hk_guide', landmark: '.hk-guide-card' },
];

test.describe('Browser test: cross-browser and mobile rendering', () => {
  test('login and register forms render their fields', async ({ page }) => {
    for (const path of ['/login', '/register']) {
      await page.goto(path);
      await expect(page.locator('form.auth-form')).toBeVisible();
      await expect(page.locator('#email')).toBeVisible();
      await expect(page.locator('#password')).toBeVisible();
      await expect(page.locator('form.auth-form button[type="submit"]')).toBeVisible();
    }
  });

  for (const { path, landmark } of AUTHED_PAGES) {
    test(`${path} renders its main landmark without app errors`, async ({ authedPage: page, baseURL }) => {
      const pageErrors: string[] = [];
      const appConsoleErrors: string[] = [];
      page.on('pageerror', (e) => pageErrors.push(e.message));
      page.on('console', (m) => {
        // Only errors raised by our own origin: third-party CDN failures in a sandbox are not our bug.
        if (m.type() === 'error' && m.location().url.startsWith(baseURL!)) appConsoleErrors.push(m.text());
      });
      await page.goto(path);
      await expect(page.locator(landmark).first()).toBeVisible();
      expect(pageErrors).toEqual([]);
      expect(appConsoleErrors).toEqual([]);
    });
  }

  test('a loading screen shows while /me is slow, then the page appears', async ({ authedPage: page }) => {
    await page.route('**/me', async (route) => {
      await new Promise((r) => setTimeout(r, 1_500));
      await route.continue();
    });
    // waitUntil opts out of the fixture's wait-for-network-idle, which would
    // otherwise sit through the delayed /me and miss the loading screen.
    await page.goto('/profile', { waitUntil: 'commit' });
    // data-testid, not the Font Awesome <i>: the icon font comes from a CDN, and
    // an empty <i> (font blocked/slow) has no box, so it never counts as visible.
    await expect(page.getByTestId('page-loading')).toBeVisible();
    await expect(page.locator('.profile-card').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('page-loading')).toHaveCount(0);
  });

  test('no horizontal overflow on login and chat (mobile-friendly layout)', async ({ authedPage: page }) => {
    for (const path of ['/login', '/']) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(1);
    }
  });
});
