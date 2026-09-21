import { defineConfig, devices } from '@playwright/test';
import { assertLocalDb, e2eDbUrl } from './tests/support/env';

// Fail before any server starts if the DB target isn't local.
const dbUrl = assertLocalDb(e2eDbUrl());

const WEB_PORT = Number(process.env.E2E_WEB_PORT || 3100);
const API_PORT = Number(process.env.E2E_API_PORT || 5100);
const baseURL = `http://127.0.0.1:${WEB_PORT}`;
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: isCI ? 1 : 2,
  retries: 1, // absorbs the proxy keep-alive race; flaky tests are still reported as flaky
  forbidOnly: isCI,
  globalSetup: './tests/e2e/global-setup.ts',
  globalTeardown: './tests/e2e/global-teardown.ts',
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
  ],
  outputDir: 'test-results',
  use: {
    baseURL,
    locale: 'en-GB',
    timezoneId: 'Asia/Hong_Kong',
    trace: 'on',
    video: 'on',
    screenshot: 'on',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  webServer: [
    {
      // uvicorn's default 5s keep-alive closes idle sockets that Next's proxy is
      // still reusing, which surfaces as "Failed to proxy ... ECONNRESET" (and a
      // 500 in the browser) about once per few hundred requests. Same app as
      // `python run.py`, just a keep-alive longer than the proxy's reuse window.
      command: `${process.env.E2E_PYTHON || 'python'} -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --timeout-keep-alive 120 --log-level warning --no-access-log`,
      env: {
        PORT: String(API_PORT),
        SKIP_ENV_LOCAL: '1',
        DATABASE_URL: dbUrl,
        SUPABASE_POOLER_URL: '',
        POSTGRES_POOLER_URL: '',
        DATABASE_POOLER_URL: '',
        // Blank every third-party credential the app reads (.env still holds a
        // real ZHIPU key; process env wins over .env because override=False).
        ZHIPU_API_KEY: '',
        NEWS_API_KEY: '',
        HF_API_KEY: '',
        AZURE_COMMUNICATION_CONNECTION_STRING: '',
        GOOGLE_CLIENT_ID: '',
        GOOGLE_CLIENT_SECRET: '',
        LOG_LEVEL: 'WARNING',
        SECRET_KEY: process.env.SECRET_KEY || 'e2e-secret-key',
      },
      url: `http://127.0.0.1:${API_PORT}/health`,
      // Never adopt a server that is already listening: a stale one could be running
      // against a different database and would bypass the local-DB guard above.
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: isCI ? `npm run build && npx next start -p ${WEB_PORT}` : `npx next dev -p ${WEB_PORT}`,
      cwd: 'web-next',
      env: { NEXT_PUBLIC_API_BASE: '', E2E_API_PROXY: `http://127.0.0.1:${API_PORT}` },
      url: baseURL,
      reuseExistingServer: false, // same reason: its proxy target is baked in at start-up
      timeout: 300_000, // CI also runs `next build` inside this command

    },
  ],
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 5'] } },
    { name: 'mobile-webkit', use: { ...devices['iPhone 13'] } },
  ],
});
