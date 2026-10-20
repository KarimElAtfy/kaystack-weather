import { defineConfig } from '@playwright/test';

const port = 4173;

export default defineConfig({
  testDir: 'tests/e2e',
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'line' : 'list',
  use: {
    baseURL: `http://localhost:${port}`,
    // Installed browsers, so nothing is downloaded: the CI runner has Google
    // Chrome and Windows has Edge.
    channel: process.env.CI ? 'chrome' : 'msedge',
    locale: 'it-IT',
    timezoneId: 'America/Los_Angeles'
  },
  webServer: {
    command: `node scripts/serve.ts build ${port}`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI
  }
});
