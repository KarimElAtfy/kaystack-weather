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
});

test('tells when the data was last checked', async ({ page }) => {
  await page.goto('/sesto-calende');
  await expect(page.locator('#refreshed')).toHaveText('Dati controllati alle 15:10.');
});
