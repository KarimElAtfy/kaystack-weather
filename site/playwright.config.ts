import { defineConfig } from '@playwright/test';

const port = 4173;

export default defineConfig({
  testDir: 'tests/e2e',
  forbidOnly: !!process.env.CI,
  // The runner has four cores and Playwright takes half by default; the
  // matrix keeps all four busy and the job inside its five minutes.
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? 'line' : 'list',
  use: {
    baseURL: `http://localhost:${port}`,
    locale: 'it-IT',
    timezoneId: 'America/Los_Angeles'
  },
  projects: [
    // The installed browser, so nothing is downloaded for it: the CI runner has
    // Google Chrome and Windows has Edge.
    { name: 'chrome', use: { channel: process.env.CI ? 'chrome' : 'msedge' } },
    // WebKit and Firefox paint what <use> clones their own way, so they run the
    // specs about the radar and the symbols.
    {
      name: 'webkit',
      use: { browserName: 'webkit', baseURL: `http://localhost:${port + 1}` },
      testMatch: /(paint|radar)\.spec\.ts/
    },
    { name: 'firefox', use: { browserName: 'firefox' }, testMatch: /(paint|radar)\.spec\.ts/ }
  ],
  webServer: [
    {
      command: `node scripts/serve.ts build ${port}`,
      url: `http://localhost:${port}`,
      reuseExistingServer: !process.env.CI
    },
    {
      command: `node scripts/serve.ts build ${port + 1} --http`,
      url: `http://localhost:${port + 1}`,
      reuseExistingServer: !process.env.CI
    }
  ]
});
