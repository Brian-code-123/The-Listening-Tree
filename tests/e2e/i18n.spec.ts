import { test, expect } from './support/fixtures';
import { setLanguage } from './support/helpers';

type PageCase = { name: string; path: string; sel: string; en: string; zh: string };

const AUTHED: PageCase[] = [
  { name: 'chat', path: '/', sel: '.user_info span', en: 'The Listening Tree', zh: '聆聽樹' },
  { name: 'history', path: '/history', sel: '.hk-guide-title', en: 'Conversation History', zh: '對話記錄' },
  { name: 'profile', path: '/profile', sel: '.profile-hero-text h1', en: 'My Profile', zh: '個人檔案' },
  { name: 'accessibility', path: '/accessibility', sel: '.accessibility-banner h1', en: 'Accessibility Settings', zh: '無障礙設定' },
  { name: 'hk_guide', path: '/hk_guide', sel: '.hk-guide-title', en: 'Hong Kong Local Guide', zh: '香港本地攻略' },
];

const PUBLIC: PageCase[] = [
  { name: 'login', path: '/login', sel: '.auth-header h2', en: 'Sign In', zh: '登入' },
  { name: 'register', path: '/register', sel: '.auth-header h2', en: 'Register', zh: '註冊' },
];

test.describe('Black-box: language switching follows the session on every page', () => {
  for (const p of AUTHED) {
    test(`${p.name} switches zh-HK <-> en`, async ({ authedPage: page }) => {
      await setLanguage(page, 'zh-HK');
      await page.goto(p.path);
      await expect(page.locator(p.sel).first()).toContainText(p.zh);
      await setLanguage(page, 'en');
      await page.goto(p.path);
      await expect(page.locator(p.sel).first()).toContainText(p.en);
    });
  }

  for (const p of PUBLIC) {
    test(`${p.name} (logged out) switches zh-HK <-> en`, async ({ page }) => {
      await setLanguage(page, 'zh-HK');
      await page.goto(p.path);
      await expect(page.locator(p.sel).first()).toContainText(p.zh);
      await setLanguage(page, 'en');
      await page.goto(p.path);
      await expect(page.locator(p.sel).first()).toContainText(p.en);
    });
  }

  test('the chat page language buttons switch language and stay on the Next origin', async ({ authedPage: page }) => {
    await page.goto('/');
    await page.locator('a[href$="/set_language/zh-HK"]').first().click();
    await expect(page.locator('.user_info span').first()).toContainText('聆聽樹');
    await expect(page).toHaveURL(/\/$/);
  });

  test('the profile page language buttons work (bare-path links need the proxy)', async ({ authedPage: page }) => {
    await page.goto('/profile');
    await page.locator('a[aria-label="繁體中文"]').click();
    // safe_redirect_target compares the Referer host with the request host, and
    // Next's proxy rewrites the Host header to the FastAPI port, so in this test
    // topology the redirect falls back to "/" instead of returning to /profile
    // (production keeps the host, so it does return). What matters here is that
    // the click reached the backend and switched the session language.
    await page.waitForLoadState('networkidle');
    await page.goto('/profile');
    await expect(page.locator('.profile-hero-text h1')).toContainText('個人檔案');
  });

  test('the password toggle label is localized', async ({ page }) => {
    await setLanguage(page, 'zh-HK');
    await page.goto('/login');
    await expect(page.locator('button[aria-label="顯示密碼"]')).toBeVisible();
  });
});
