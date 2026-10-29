// The built site as visitors get it: it asks only itself and the public
// account, and the development clock override in the address does nothing.
import { expect, test } from '@playwright/test';
import { ACCOUNT, openState, TOWNS } from './fixtures.ts';

for (const town of TOWNS) {
  test(`/${town} asks only the site and the public account`, async ({ page, baseURL }) => {
    const asked: string[] = [];
    page.on('request', (request) => asked.push(request.url()));
    await page.setViewportSize({ width: 1280, height: 900 });
    await openState(page, 'pioggia', `/${town}`, baseURL ?? '');
    await page.getByText('Stato delle fonti').click();
    await expect(page.locator('#sources .srcs li')).toHaveCount(4);
    const elsewhere = asked.filter(
      (url) => !url.startsWith(`${baseURL}/`) && !url.startsWith(`${ACCOUNT}/public/`)
    );
    expect(elsewhere).toEqual([]);
    expect(asked.filter((url) => /\/data\/|fixtures/.test(url))).toEqual([]);
    expect(asked.some((url) => url.endsWith(`/public/v1/${town}/forecast.json`))).toBe(true);
  });
}

test('ignores the clock set in the address', async ({ page, baseURL }) => {
  await openState(page, 'pioggia', '/pedrengo?now=2026-10-26T09:00:00Z', baseURL ?? '');
  await expect(page.locator('#statusline')).toHaveText('Aggiornata alle 14:00 (1 h 10 min fa).');
});

test("ships none of Kit's data files, so no page has a folder twin", async ({ request }) => {
  for (const url of ['/__data.json', '/pedrengo/__data.json', '/privacy/__data.json']) {
    expect((await request.get(url)).status()).toBe(404);
  }
});
