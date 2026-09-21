import { test, expect } from './support/fixtures';
import { setLanguage } from './support/helpers';

test.describe('Black-box: Hong Kong local guide', () => {
  test('shows five category tabs and cards', async ({ authedPage: page }) => {
    await page.goto('/hk_guide');
    await expect(page.locator('.hk-tab')).toHaveCount(5);
    await expect(page.locator('.hk-guide-card').first()).toBeVisible();
  });

  test('picking a category filters every card to that category', async ({ authedPage: page }) => {
    await page.goto('/hk_guide');
    await expect(page.locator('.hk-guide-card').first()).toBeVisible();
    const all = await page.locator('.hk-guide-card').count();
    await page.locator('.hk-tab').nth(1).click();
    const badges = await page.locator('.hk-card-badge').allTextContents();
    expect(badges.length).toBeGreaterThan(0);
    expect(badges.length).toBeLessThan(all);
    expect(new Set(badges.map((b) => b.trim())).size).toBe(1);
  });

  test('"Read more" opens the detail modal and Escape closes it', async ({ authedPage: page }) => {
    await page.goto('/hk_guide');
    await page.locator('.hk-card-detail').first().click();
    await expect(page.locator('.hk-guide-modal.show')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('.hk-guide-modal.show')).toHaveCount(0);
  });

  test('the "Last updated" label is localized', async ({ authedPage: page }) => {
    await setLanguage(page, 'zh-HK');
    await page.goto('/hk_guide');
    await expect(page.locator('.hk-guide-update-bar')).toContainText('最後更新');
  });
});
