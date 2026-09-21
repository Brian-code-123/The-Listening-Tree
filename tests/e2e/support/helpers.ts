import type { Page } from '@playwright/test';

// Set the session language without navigating. /set_language/* is a 303
// redirect endpoint; page.goto()-ing it from a logged-out page races with the
// app's own client-side redirect to /login. The context's request API shares
// the browser cookie jar, so the session cookie lands in the page's context.
export async function setLanguage(page: Page, lang: 'en' | 'zh-HK') {
  const res = await page.context().request.get(`/set_language/${lang}`);
  if (!res.ok()) throw new Error(`setLanguage(${lang}) failed: ${res.status()}`);
}

// On phone-sized viewports the chat sidebar (conversations, calendar,
// reminders) is collapsed behind a toggle in the header (`d-lg-none`).
export async function openSidebarIfMobile(page: Page) {
  const toggle = page.locator('button.d-lg-none').first();
  if (await toggle.isVisible()) await toggle.click();
}
