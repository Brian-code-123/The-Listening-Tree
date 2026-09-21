import { test as base, expect, type Page } from '@playwright/test';
import { createUser, deleteUser, loginViaApi, type TestUser } from '../../support/users';

type Fixtures = { user: TestUser; authedPage: Page };

export const test = base.extend<Fixtures>({
  // After every navigation, wait for the network to go idle so React has
  // hydrated before a test types into a controlled input or clicks a form
  // button: pre-hydration, a submit is a native GET (e.g. "/login?") and typed
  // values can be reset. Pass an explicit `waitUntil` to opt out (e.g. to
  // observe a loading screen).
  page: async ({ page }, use) => {
    // Hermetic: never touch the internet. A hung third-party request (seen: the
    // Vercel Analytics script) blocks the page "load" event and times out
    // page.goto, and test runs must not send analytics events anyway. Fonts and
    // icon CSS from CDNs fall back to system fonts, which no test depends on.
    await page.route(
      (url) => url.hostname !== '127.0.0.1' && url.hostname !== 'localhost',
      (route) => route.abort(),
    );
    // /_vercel/* (Analytics script) is served by the Vercel platform, so a local
    // production build answers 404 and logs a console error. Serve an empty script.
    await page.route('**/_vercel/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/javascript', body: '' }),
    );
    const goto = page.goto.bind(page);
    page.goto = (async (url: string, options?: Parameters<Page['goto']>[1]) => {
      const response = await goto(url, options);
      if (!options?.waitUntil) await page.waitForLoadState('networkidle').catch(() => {});
      return response;
    }) as Page['goto'];
    await use(page);
  },
  user: async ({}, use, testInfo) => {
    const user = await createUser(testInfo.project.use.baseURL as string, testInfo.project.name);
    await use(user);
    await deleteUser(user.email);
  },
  authedPage: async ({ page, user }, use) => {
    await loginViaApi(page, user);
    await use(page);
  },
});

export { expect };
