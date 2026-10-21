// Every page in every state, at the three widths and in both themes: no policy
// violation or console error, WCAG 2.2 AA by axe, no sideways scroll, and no
// layout shift when the data arrives.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import {
  countShifts,
  freezeClock,
  openState,
  SCENARIOS,
  STATES,
  TOWNS,
  useScenario,
  watch
} from './fixtures.ts';

test.describe.configure({ mode: 'parallel' });

const WIDTHS = [320, 360, 1280];
const SCHEMES = ['light', 'dark'] as const;
const TEXT_PAGES = ['/', '/come-funziona', '/fonti-e-licenze', '/privacy', '/404'];

async function accessible(page: Page) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  return violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}

const sideways = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

// In lines: the status line keeps room for two whatever it says.
const statusLines = (page: Page) =>
  page
    .locator('#statusline')
    .evaluate(
      (line) => line.getBoundingClientRect().height / parseFloat(getComputedStyle(line).lineHeight)
    );

for (const scheme of SCHEMES) {
  for (const width of WIDTHS) {
    test.describe(`${width} px, ${scheme}`, () => {
      test.use({ viewport: { width, height: 800 }, colorScheme: scheme });

      for (const town of TOWNS) {
        for (const state of STATES) {
          test(`/${town} ${state}`, async ({ page, baseURL }) => {
            const problems = await watch(page);
            const shifted = await countShifts(page);
            await openState(page, state, `/${town}`, baseURL ?? '');
            expect(await shifted()).toBeLessThan(0.01);
            expect(await statusLines(page)).toBe(2);
            expect(await sideways(page)).toBe(0);
            expect(await accessible(page)).toEqual([]);
            if (state !== 'caricamento') {
              await page.getByRole('button', { name: 'Tabella' }).click();
              expect(await sideways(page)).toBe(0);
              expect(await accessible(page)).toEqual([]);
            }
            expect(problems).toEqual([]);
          });
        }
      }

      for (const url of TEXT_PAGES) {
        test(url, async ({ page, context, baseURL }) => {
          const problems = await watch(page);
          await useScenario(context, 'pioggia', baseURL ?? '');
          await freezeClock(page);
          await page.goto(url, { waitUntil: 'networkidle' });
          expect(await sideways(page)).toBe(0);
          expect(await accessible(page)).toEqual([]);
          expect(problems).toEqual([]);
        });
      }
    });
  }
}

// On a phone the radar reads its images only once scrolled to, while someone
// is looking at it: nothing may move then either.
for (const width of [320, 360]) {
  for (const town of TOWNS) {
    for (const scenario of SCENARIOS) {
      test(`/${town} ${scenario} at ${width} px, scrolled to the radar`, async ({
        page,
        baseURL
      }) => {
        await page.setViewportSize({ width, height: 800 });
        const shifted = await countShifts(page);
        await openState(page, scenario, `/${town}`, baseURL ?? '');
        // To the end of the page: the radar's legend and credits, and the
        // footer under them, are in view when the images arrive.
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await expect(page.locator('#radar .stamp, #radar .map-empty')).toBeVisible();
        await page.waitForLoadState('networkidle');
        expect(await shifted()).toBeLessThan(0.01);
      });
    }
  }
}
