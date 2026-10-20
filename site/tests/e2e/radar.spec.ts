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
  await slider.focus();
  await page.keyboard.press('Home');
  for (let i = 0; i < 7; i++) await page.keyboard.press('ArrowRight');
  await expect(page.locator('#radar .rsum')).toHaveText('14:00, immagine mancante');
  await expect(slider).toHaveAttribute('aria-valuetext', '14:00, immagine mancante');
  await expect(page.locator('#radar .missing')).toBeVisible();
});

test('never shows an empty map as if it were dry', async ({ page, baseURL }) => {
  await open(page, 'mancanti', '/pedrengo', baseURL ?? '');
  await expect(page.locator('#radar .map-empty')).toContainText('Radar non disponibile.');
  await expect(page.locator('#radar .map')).toHaveCount(0);
});
