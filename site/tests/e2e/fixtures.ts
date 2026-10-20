// Answers the public account from tests/fixtures/<scenario>, with the CORS
// headers the account sends to the site, and sets the page clock to the
// fixtures' Saturday, 24 October 2026 at 15:10 in Rome.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { BrowserContext, Page } from '@playwright/test';

export const ACCOUNT = 'https://stkaystackmeteopubprod.blob.core.windows.net';
export const NOW = new Date('2026-10-24T13:10:00Z');
export const SCENARIOS = ['pioggia', 'asciutto', 'vecchi', 'mancanti'] as const;
export type Scenario = (typeof SCENARIOS)[number];

export async function useScenario(context: BrowserContext, scenario: Scenario, origin: string) {
  // The radar maps come from the pipeline later; the stand-ins answer for them.
  await context.route(`${origin}/radar/*.svg`, (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: readFileSync(
        join('tests/fixtures/maps', new URL(route.request().url()).pathname.slice(7))
      )
    })
  );
  await context.route(`${ACCOUNT}/public/**`, (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/public\//, '');
    const file = join('tests/fixtures', scenario, path);
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-expose-headers': 'ETag',
      'cache-control': 'public, max-age=60'
    };
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
