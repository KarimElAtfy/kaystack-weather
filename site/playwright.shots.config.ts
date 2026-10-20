// `npm run shots`: screenshots for the designer's review, never asserted.
import { defineConfig } from '@playwright/test';
import base from './playwright.config.ts';

export default defineConfig({
  ...base,
  testDir: 'tests/shots',
  fullyParallel: true,
  reporter: 'line'
});
