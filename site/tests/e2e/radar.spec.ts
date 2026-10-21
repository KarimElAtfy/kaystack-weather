import { expect, test, type Page } from '@playwright/test';
import { freezeClock, useScenario, type Scenario } from './fixtures.ts';

async function open(page: Page, scenario: Scenario, url: string, origin: string) {
  await useScenario(page.context(), scenario, origin);
  await freezeClock(page);
  await page.goto(url);
  await page.locator('#radar').scrollIntoViewIfNeeded();
}

test('shows the last frame first and paints its rain', async ({ page, baseURL }) => {
  await open(page, 'pioggia', '/sesto-calende', baseURL ?? '');
  await expect(page.locator('#radar .stamp')).toContainText('15:05');
  await expect(page.locator('#radar .rsum')).toContainText('Alle 15:05:');
  const painted = await page.locator('#radar canvas').evaluate((canvas: HTMLCanvasElement) => {
    const pixels = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) count++;
    return count;
  });
  expect(painted).toBeGreaterThan(100);
});

test('plays only when asked and steps with the slider', async ({ page, baseURL }) => {
  await open(page, 'pioggia', '/pedrengo', baseURL ?? '');
  const play = page.getByRole('button', { name: 'Avvia' });
  await expect(play).not.toHaveAttribute('aria-pressed');
  await expect(page.getByRole('button', { name: 'Ultima' })).toBeDisabled();
  const slider = page.getByRole('slider', { name: "Ora dell'immagine" });
  await expect(slider).toBeEnabled();
  await slider.focus();
  await page.keyboard.press('Home');
  await expect(slider).toHaveAttribute('aria-valuetext', /^Alle 14:10: sul paese /);
  await expect(page.locator('#radar .rsum')).toContainText('Alle 14:10:');
  await play.click();
  await expect(page.getByRole('button', { name: 'Ferma' })).toBeVisible();
});

test('says when a frame is missing', async ({ page, baseURL }) => {
  await open(page, 'vecchi', '/pedrengo', baseURL ?? '');
  await expect(page.locator('#radar .note')).toContainText('Il radar non si aggiorna dalle 14:20');
  const slider = page.getByRole('slider', { name: "Ora dell'immagine" });
  await expect(slider).toBeEnabled();
  await slider.focus();
  await page.keyboard.press('Home');
  for (let i = 0; i < 7; i++) await page.keyboard.press('ArrowRight');
  await expect(page.locator('#radar .rsum')).toHaveText('14:00, immagine mancante');
  await expect(slider).toHaveAttribute('aria-valuetext', '14:00, immagine mancante');
  await expect(page.locator('#radar .veil')).toBeVisible();
  await expect(page.locator('#radar .veil-box')).toHaveText("Manca l'immagine delle 14:00.");
});

test('never shows an empty map as if it were dry', async ({ page, baseURL }) => {
  await open(page, 'mancanti', '/pedrengo', baseURL ?? '');
  await expect(page.locator('#radar .map-empty')).toContainText('Radar non disponibile.');
  await expect(page.locator('#radar .map')).toHaveCount(0);
});

test('veils the map until its images are drawn', async ({ page, context, baseURL }) => {
  await useScenario(context, 'pioggia', baseURL ?? '');
  await freezeClock(page);
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await context.route('**/radar-*.png', async (route) => {
    await held;
    await route.fallback();
  });
  await page.goto('/sesto-calende');
  await page.locator('#radar').scrollIntoViewIfNeeded();
  await expect(page.locator('#radar .veil-box')).toHaveText('Carico le immagini');
  await expect(page.locator('#radar .stamp')).toHaveCount(0);
  await expect(page.locator('#radar .ftime')).toHaveText('');
  const slider = page.getByRole('slider', { name: "Ora dell'immagine" });
  await expect(slider).toBeDisabled();
  await expect(slider).toHaveAttribute('aria-valuetext', 'Carico le immagini');
  release();
  await expect(page.locator('#radar .veil')).toHaveCount(0);
  await expect(page.locator('#radar .stamp')).toContainText('15:05');
});

for (const [slug, name] of [
  ['pedrengo', 'Pedrengo'],
  ['sesto-calende', 'Sesto Calende']
]) {
  for (const width of [320, 360, 1280]) {
    test(`keeps ${name} and the scale bar clear of the message at ${width} px`, async ({
      page,
      baseURL
    }) => {
      await page.setViewportSize({ width, height: 800 });
      await open(page, 'vecchi', `/${slug}`, baseURL ?? '');
      const slider = page.getByRole('slider', { name: "Ora dell'immagine" });
      await expect(slider).toBeEnabled();
      await slider.focus();
      await page.keyboard.press('Home');
      for (let i = 0; i < 7; i++) await page.keyboard.press('ArrowRight');
      const box = await page.locator('#radar .veil-box p').boundingBox();
      const label = await page.locator('#radar .map text', { hasText: name }).boundingBox();
      const marker = await page.locator('#radar .town-halo').boundingBox();
      for (const above of [label, marker]) {
        expect((above?.y ?? 0) + (above?.height ?? 0)).toBeLessThan(box?.y ?? 0);
      }
      const bar = await page.locator('#radar .bar-back').boundingBox();
      const apart =
        (box?.x ?? 0) + (box?.width ?? 0) + 4 <= (bar?.x ?? 0) ||
        (box?.y ?? 0) + (box?.height ?? 0) + 4 <= (bar?.y ?? 0);
      expect(apart).toBe(true);
    });
  }
}
