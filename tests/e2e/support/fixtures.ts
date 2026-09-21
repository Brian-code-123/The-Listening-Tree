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
