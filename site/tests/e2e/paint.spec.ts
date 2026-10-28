// The symbols and the base map are drawn by <use> and coloured by the page's
// tokens. When an engine loses the tokens it paints them black, which only the
// pixels show: the DOM and the computed styles look the same either way.
import { expect, test, type Locator, type Page } from '@playwright/test';
import { freezeClock, useScenario, type Scenario } from './fixtures.ts';

type Shares = { black: number; token: number };

async function open(page: Page, scenario: Scenario, origin: string) {
  await useScenario(page.context(), scenario, origin);
  await freezeClock(page);
  await page.goto('/pedrengo');
  await expect(page.locator('#refreshed')).toContainText('Dati controllati');
}

// The share of the element's pixels that are black, and of those within a few
// levels of the token's colour. The page's policy refuses data: images, so the
// screenshot is read in a blank page.
async function shares(page: Page, target: Locator, token: string): Promise<Shares> {
  const colour = await page.evaluate(
    (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim(),
    token
  );
  const png = (await target.screenshot()).toString('base64');
  const blank = await page.context().newPage();
  const found = await blank.evaluate(
    async ({ png, colour }) => {
      const image = new Image();
      image.src = `data:image/png;base64,${png}`;
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext('2d', { willReadFrequently: true })!;
      context.fillStyle = colour;
      context.fillRect(0, 0, 1, 1);
      const want = [...context.getImageData(0, 0, 1, 1).data];
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, image.width, image.height).data;
      let black = 0;
      let token = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        const rgb = [pixels[i]!, pixels[i + 1]!, pixels[i + 2]!];
        if (Math.max(...rgb) <= 16) black++;
        if (rgb.every((v, k) => Math.abs(v - want[k]!) <= 6)) token++;
      }
      const total = pixels.length / 4;
      return { black: black / total, token: token / total };
    },
    { png, colour }
  );
  await blank.close();
  return found;
}

for (const scheme of ['light', 'dark'] as const) {
  test.describe(scheme, () => {
    test.use({ colorScheme: scheme, viewport: { width: 390, height: 844 } });

    test('paints the land of the radar map', async ({ page, baseURL }) => {
      await open(page, 'asciutto', baseURL ?? '');
      const map = page.locator('#radar .map');
      await map.scrollIntoViewIfNeeded();
      await expect(page.locator('#radar .stamp')).toBeVisible();
      // Black land leaves the token's colour nowhere: the rings and labels cover little.
      expect((await shares(page, map, '--map-land')).token).toBeGreaterThan(0.5);
    });

    test('paints the clouds of the weather symbols', async ({ page, baseURL }) => {
      await open(page, 'pioggia', baseURL ?? '');
      const days = page.locator('#giorni-10 table.days');
      await days.scrollIntoViewIfNeeded();
      const found = await shares(page, days, '--sym-cloud');
      expect(found.black).toBeLessThan(0.001);
      expect(found.token).toBeGreaterThan(0.005);
    });
  });
}
