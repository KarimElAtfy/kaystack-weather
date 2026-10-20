// Answers the public account from tests/fixtures/<scenario>, with the CORS
// headers the account sends to the site, and sets the page clock to the
// fixtures' Saturday, 24 October 2026 at 15:10 in Rome.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, type BrowserContext, type Page } from '@playwright/test';

export const ACCOUNT = 'https://stkaystackmeteopubprod.blob.core.windows.net';
export const NOW = new Date('2026-10-24T13:10:00Z');
export const SCENARIOS = ['pioggia', 'asciutto', 'vecchi', 'mancanti'] as const;
export type Scenario = (typeof SCENARIOS)[number];
// The fixture scenarios, plus a device gone offline after the first reads and
// a page whose reads have not answered yet.
export const STATES = [...SCENARIOS, 'offline', 'caricamento'] as const;
export type State = (typeof STATES)[number];
export const TOWNS = ['pedrengo', 'sesto-calende'] as const;

// The radar maps come from the pipeline later; the stand-ins answer for them.
async function useMaps(context: BrowserContext, origin: string) {
  await context.route(`${origin}/radar/*.svg`, (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: readFileSync(
        join('tests/fixtures/maps', new URL(route.request().url()).pathname.slice(7))
      )
    })
  );
}

// `delay` holds each answer back, as the network does, so the swap from
// placeholders to data happens after the first paint.
export async function useScenario(
  context: BrowserContext,
  scenario: Scenario,
  origin: string,
  delay = 0
) {
  await useMaps(context, origin);
  await context.route(`${ACCOUNT}/public/**`, async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/public\//, '');
    const file = join('tests/fixtures', scenario, path);
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-expose-headers': 'ETag',
      'cache-control': 'public, max-age=60'
    };
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
    if (!existsSync(file)) return route.fulfill({ status: 404, headers, body: '' });
    return route.fulfill({
      status: 200,
      headers,
      contentType: file.endsWith('.json') ? 'application/json' : 'image/png',
      body: readFileSync(file)
    });
  });
}

export const freezeClock = (page: Page) => page.clock.install({ time: NOW });

// Opens a town page in one of the states and waits until it has settled.
export async function openState(page: Page, state: State, url: string, origin: string) {
  const context = page.context();
  if (state === 'caricamento') {
    await useMaps(context, origin);
    // Never answered: the requests stay pending for the whole test.
    await context.route(`${ACCOUNT}/public/**`, () => {});
  } else {
    await useScenario(context, state === 'offline' ? 'pioggia' : state, origin, 300);
  }
  await freezeClock(page);
  await page.goto(url);
  if (state === 'caricamento') {
    await expect(page.locator('#statusline')).toHaveText('Carico i dati');
    return;
  }
  await expect(page.locator('#refreshed')).toContainText('Dati controllati');
  await page.waitForLoadState('networkidle');
  if (state === 'offline') {
    await context.setOffline(true);
    // Past the next due read, which finds the device offline.
    await page.clock.runFor(10 * 60_000);
    await expect(page.locator('#statusline')).toContainText('Sei offline');
  }
}

// Collects what must never happen on a page: a policy violation, an error in
// the console or an uncaught exception. A read of the account that fails is
// what some states are about, so the browser's line for it does not count.
export async function watch(page: Page): Promise<string[]> {
  const problems: string[] = [];
  await page.exposeFunction('reportViolation', (text: string) => problems.push(text));
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) => {
      const report = (window as unknown as { reportViolation: (text: string) => void })
        .reportViolation;
      report(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const failedRead =
      message.text().startsWith('Failed to load resource') &&
      message.location().url.startsWith(`${ACCOUNT}/`);
    if (!failedRead) problems.push(message.text());
  });
  page.on('pageerror', (error) => problems.push(error.message));
  return problems;
}

// Sums the layout shifts not caused by input, from the first paint on.
export async function countShifts(page: Page) {
  await page.addInitScript(() => {
    const total = window as unknown as { shifted: number };
    total.shifted = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & {
        value: number;
        hadRecentInput: boolean;
      })[]) {
        if (!entry.hadRecentInput) total.shifted += entry.value;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });
  return () => page.evaluate(() => (window as unknown as { shifted: number }).shifted);
}
