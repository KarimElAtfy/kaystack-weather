// Every state of both towns and every text page, at 360 and 1280 px in both
// themes, saved as full pages under shots/ for the design review. The fonts
// differ between machines, so nothing here is compared.
import { test } from '@playwright/test';
import { freezeClock, openState, STATES, TOWNS, useScenario } from '../e2e/fixtures.ts';

const TEXT_PAGES = ['/', '/come-funziona', '/fonti-e-licenze', '/privacy', '/404'];

for (const scheme of ['light', 'dark'] as const) {
  for (const width of [360, 1280]) {
    test.describe(`${width} ${scheme}`, () => {
      test.use({ viewport: { width, height: 800 }, colorScheme: scheme });
      const name = (page: string) => `shots/${page}-${width}-${scheme}.png`;

      for (const town of TOWNS) {
        for (const state of STATES) {
          test(`${town} ${state}`, async ({ page, baseURL }) => {
            await openState(page, state, `/${town}`, baseURL ?? '');
            // The radar paints only once near the screen.
            await page.locator('#radar').scrollIntoViewIfNeeded();
            await page.waitForLoadState('networkidle');
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({ path: name(`${town}-${state}`), fullPage: true });
          });
        }
      }

      for (const url of TEXT_PAGES) {
        test(url, async ({ page, context, baseURL }) => {
          await useScenario(context, 'pioggia', baseURL ?? '');
          await freezeClock(page);
          await page.goto(url, { waitUntil: 'networkidle' });
          const file = url === '/' ? 'selettore' : url.slice(1);
          await page.screenshot({ path: name(file), fullPage: true });
        });
      }
    });
  }
}
