import { expect, test } from '@playwright/test';
import { freezeClock, useScenario } from './fixtures.ts';

test.beforeEach(async ({ page, context, baseURL }) => {
  await useScenario(context, 'pioggia', baseURL ?? '');
  await freezeClock(page);
});

test('says when the forecast was issued, in Rome time', async ({ page }) => {
  await page.goto('/pedrengo');
  await expect(page.locator('#issued')).toHaveText('Emessa alle 14:00, 1 h 10 min fa.');
  await expect(page.locator('.trust strong')).toHaveText('Torre Boldone');
  await expect(page.locator('#adesso .src').first()).toContainText(
    'Aeroporto di Orio al Serio, a 4,3 km.'
  );
});

test('tells when the data was last checked', async ({ page }) => {
  await page.goto('/sesto-calende');
  await expect(page.locator('#refreshed')).toHaveText('Dati controllati alle 15:10.');
});

test('reads the chosen hour aloud as it moves', async ({ page }) => {
  await page.goto('/pedrengo');
  const hour = page.getByRole('slider', { name: 'Ora del grafico' });
  await hour.focus();
  const before = await hour.getAttribute('aria-valuetext');
  await page.keyboard.press('ArrowRight');
  const after = await hour.getAttribute('aria-valuetext');
  expect(before).toMatch(/^sabato 24, 16:00, \d+ °C modelli da/);
  expect(after).toMatch(/^sabato 24, 17:00, /);
});

test('labels both 02:00 of the night summer time ends', async ({ page }) => {
  await page.goto('/pedrengo');
  const hour = page.getByRole('slider', { name: 'Ora del grafico' });
  await hour.focus();
  for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowRight');
  await expect(hour).toHaveAttribute('aria-valuetext', /^domenica 25, 02:00 \(ora legale\), /);
  await page.keyboard.press('ArrowRight');
  await expect(hour).toHaveAttribute('aria-valuetext', /^domenica 25, 02:00 \(ora solare\), /);
  await page.getByRole('button', { name: 'Tabella' }).click();
  await expect(page.locator('tbody th[scope="row"]', { hasText: 'ora legale' })).toHaveCount(1);
  await expect(page.locator('tbody th[scope="row"]', { hasText: 'ora solare' })).toHaveCount(1);
});

test('warns about an old forecast and says which source stopped', async ({
  page,
  context,
  baseURL
}) => {
  await context.unrouteAll();
  await useScenario(context, 'vecchi', baseURL ?? '');
  await page.goto('/pedrengo');
  await expect(page.locator('#banners .banner')).toContainText('La previsione è delle 07:00');
  await expect(page.locator('#banners .banner')).toContainText('Open-Meteo');
  await expect(page.locator('#sources details')).toHaveAttribute('open', '');
});

test('shows what is missing instead of empty space', async ({ page, context, baseURL }) => {
  await context.unrouteAll();
  await useScenario(context, 'mancanti', baseURL ?? '');
  await page.goto('/sesto-calende');
  await expect(page.locator('#adesso')).toContainText('Il radar non è disponibile');
  await expect(page.locator('#ore-48 .foot')).toContainText('Mancano alcune ore');
});

test('reads the sources when the list is opened on fresh data', async ({ page }) => {
  await page.goto('/pedrengo');
  await page.getByText('Stato delle fonti').click();
  await expect(page.locator('#sources .srcs li')).toHaveCount(4);
  await expect(page.locator('#sources .srcs li').last()).toContainText(
    'Dati delle 07:20, 7 ore fa. Arrivano con 3-9 ore di ritardo'
  );
});
