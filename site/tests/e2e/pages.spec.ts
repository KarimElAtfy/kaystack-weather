import { expect, test } from '@playwright/test';
import { freezeClock, useScenario } from './fixtures.ts';

test.beforeEach(async ({ page, context, baseURL }) => {
  await useScenario(context, 'pioggia', baseURL ?? '');
  await freezeClock(page);
});

test('shows both towns on a first visit', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.towncard')).toHaveCount(2);
  await expect(page.locator('.towncard').first()).toContainText('Torre Boldone, a 3,4 km');
});

test('keeps the footer at the bottom of a short page', async ({ page }) => {
  await page.goto('/');
  const footer = await page.locator('.site-foot').boundingBox();
  expect(Math.round((footer?.y ?? 0) + (footer?.height ?? 0))).toBe(page.viewportSize()?.height);
});

test('opens the town chosen last time, without a history entry', async ({ page }) => {
  await page.goto('/sesto-calende');
  await page.goto('/privacy');
  await page.goto('/');
  await expect(page).toHaveURL(/\/sesto-calende$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/privacy$/);
});

test('ignores a remembered town that does not exist', async ({ page }) => {
  await page.goto('/privacy');
  await page.evaluate(() => localStorage.setItem('meteo.town', 'milano'));
  await page.goto('/');
  await expect(page.locator('h1')).toHaveText('Che tempo fa?');
});

test('links back to the remembered town from a text page', async ({ page }) => {
  await page.goto('/pedrengo');
  await page.goto('/fonti-e-licenze');
  await expect(page.getByRole('link', { name: 'Torna a Pedrengo' })).toHaveAttribute(
    'href',
    '/pedrengo'
  );
});

test('answers the station question where the town page points', async ({ page }) => {
  await page.goto('/pedrengo');
  await page.getByRole('link', { name: 'Perché una stazione' }).click();
  await expect(page).toHaveURL(/\/come-funziona#stazione$/);
  await expect(page.locator('#stazione')).toHaveText('Perché una stazione');
});

test('answers an unknown address with a 404 that leads to the towns', async ({ page }) => {
  const response = await page.goto('/milano');
  expect(response?.status()).toBe(404);
  await expect(page.locator('h1')).toHaveText('Pagina non trovata');
  await expect(page.getByRole('link', { name: 'Sesto Calende' }).last()).toHaveAttribute(
    'href',
    '/sesto-calende'
  );
});
