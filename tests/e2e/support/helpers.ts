import { expect, type Page } from '@playwright/test';

// Set the session language without navigating. /set_language/* is a 303
// redirect endpoint; page.goto()-ing it from a logged-out page races with the
// app's own client-side redirect to /login. The context's request API shares
// the browser cookie jar, so the session cookie lands in the page's context.
// WebKit can apply that Set-Cookie late (a following page request still sent the
// old cookie once in ~250 runs), so confirm through /me and repeat until it holds.
export async function setLanguage(page: Page, lang: 'en' | 'zh-HK') {
  const request = page.context().request;
  await expect
    .poll(
      async () => {
        await request.get(`/set_language/${lang}`);
        return (await (await request.get('/me')).json()).lang;
      },
      { message: `session language should become ${lang}`, timeout: 10_000 },
    )
    .toBe(lang);
}

// On phone-sized viewports the chat sidebar (conversations, calendar,
// reminders) is collapsed behind a toggle in the header (`d-lg-none`).
export async function openSidebarIfMobile(page: Page) {
  const toggle = page.locator('button.d-lg-none').first();
  if (await toggle.isVisible()) await toggle.click();
}
