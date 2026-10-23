import { test, expect } from './support/fixtures';
import { loginViaApi } from '../support/users';

test.describe('Black-box: sessions end on the server, not just in the browser', () => {
  test('logging out kills a copy of the session cookie', async ({ authedPage: page, browser }, testInfo) => {
    const baseURL = testInfo.project.use.baseURL as string;
    const cookies = await page.context().cookies();
    await page.goto('/');
    await page.getByRole('button', { name: /logout|登出/i }).first().click();
    await expect(page).toHaveURL(/\/login$/);

    const copy = await browser.newContext({ baseURL });
    await copy.addCookies(cookies);
    expect((await copy.request.get('/me')).status()).toBe(401);
    await copy.close();
  });

  test('changing the password signs every other browser out', async ({ authedPage: page, user, browser }, testInfo) => {
    const baseURL = testInfo.project.use.baseURL as string;
    const other = await browser.newContext({ baseURL });
    await loginViaApi(await other.newPage(), user);
    expect((await other.request.get('/me')).status()).toBe(200);

    const change = await page.context().request.post('/profile/password', {
      form: { current_password: user.password, new_password: 'Another-Pass-12345', confirm_new_password: 'Another-Pass-12345' },
    });
    expect((await change.json()).success).toBe(true);

    expect((await page.context().request.get('/me')).status()).toBe(200); // the browser that changed it stays in
    expect((await other.request.get('/me')).status()).toBe(401);
    await other.close();
  });
});

test.describe('Black-box: browser security headers', () => {
  test('Next pages carry the security headers', async ({ page }) => {
    const res = await page.goto('/login');
    const headers = res!.headers();
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-frame-options']).toBe('DENY');
    expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
    expect(headers['permissions-policy']).toContain('microphone=(self)');
    // The CSP is production-only (a `next dev` server needs eval), so it is
    // checked where the suite runs against a production build, i.e. in CI.
    if (process.env.CI) {
      expect(headers['content-security-policy-report-only'] ?? headers['content-security-policy']).toContain("default-src 'self'");
    }
  });

  test('every page loads without a Content-Security-Policy violation', async ({ authedPage: page }) => {
    // The browser's own `securitypolicyviolation` event, not console text: WebKit also
    // prints harmless notices about the policy itself (such as "frame-ancestors is
    // ignored in a report-only policy"), and those are not violations.
    await page.addInitScript(() => {
      const seen: string[] = [];
      (window as unknown as { __csp: string[] }).__csp = seen;
      document.addEventListener('securitypolicyviolation', (e) => seen.push(`${e.violatedDirective} blocked ${e.blockedURI}`));
    });
    const violations: string[] = [];
    const collect = async () => {
      await page.waitForLoadState('networkidle');
      violations.push(...(await page.evaluate(() => (window as unknown as { __csp: string[] }).__csp)));
    };
    for (const path of ['/', '/history', '/profile', '/accessibility', '/hk_guide']) {
      await page.goto(path);
      await collect();
    }
    await page.context().clearCookies();
    for (const path of ['/login', '/register']) {
      await page.goto(path);
      await collect();
    }
    expect(violations).toEqual([]);
  });
});

test('privacy notice is public and registration needs consent', async ({ page }) => {
  await page.goto('/privacy');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.goto('/register');
  await expect(page.locator('#consent')).toBeVisible();
  await expect(page.locator('#consent')).toHaveAttribute('required', '');
});
