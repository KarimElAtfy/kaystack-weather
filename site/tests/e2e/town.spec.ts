import { expect, test } from '@playwright/test';
import { ACCOUNT, freezeClock, NOW, useScenario } from './fixtures.ts';

test.beforeEach(async ({ page, context, baseURL }) => {
  await useScenario(context, 'pioggia', baseURL ?? '');
  await freezeClock(page);
});

test('says when the forecast was issued, in Rome time', async ({ page }) => {
  await page.goto('/pedrengo');
  await expect(page.locator('#statusline')).toHaveText('Emessa alle 14:00, 1 h 10 min fa.');
  await expect(page.locator('.trust strong')).toHaveText('Torre Boldone');
  await expect(page.locator('#adesso .src').first()).toContainText(
    'Aeroporto di Orio al Serio, a 4,3 km.'
  );
});

test('lets the radar speak for now, and the models for the hours ahead', async ({ page }) => {
  await page.goto('/pedrengo');
  await expect(page.locator('#ore-48 .summary')).toHaveText(
    /^Adesso piove sul paese\. Pioggia per la maggior parte dei modelli dalle 17:00\. /
  );
  await page.goto('/sesto-calende');
  await expect(page.locator('#ore-48 .summary')).toHaveText(/^Adesso non piove sul paese\. /);
});

test('says nothing about now when the radar is old', async ({ page, context, baseURL }) => {
  await context.unrouteAll();
  await useScenario(context, 'vecchi', baseURL ?? '');
  await page.goto('/pedrengo');
  await expect(page.locator('#ore-48 .summary')).toHaveText(/^Pioggia per /);
  await expect(page.locator('#ore-48 .summary')).not.toContainText('Adesso');
});

test('tells when the data was last checked', async ({ page }) => {
  await page.goto('/sesto-calende');
  await expect(page.locator('#refreshed')).toHaveText('Dati controllati alle 15:10.');
});

test('warns about a late forecast on the status line, the sources say why', async ({
  page,
  context,
  baseURL
}) => {
  await context.unrouteAll();
  await useScenario(context, 'vecchi', baseURL ?? '');
  await page.goto('/pedrengo');
  await expect(page.locator('#statusline .warn')).toHaveText(
    'Emessa alle 07:00, 8 ore fa: di solito si aggiorna ogni ora.'
  );
  await expect(page.locator('#announce')).toHaveText('La previsione non è aggiornata.');
  await expect(page.locator('#sources details')).toHaveAttribute('open', '');
  await expect(page.locator('#sources li', { hasText: 'Open-Meteo' })).toContainText('ferma');
});

test('calls a forecast older than a day old', async ({ page }) => {
  await page.clock.setFixedTime(new Date(NOW.getTime() + 25 * 3_600_000));
  await page.goto('/pedrengo');
  await expect(page.locator('#statusline .bad')).toHaveText(
    'Previsione vecchia: emessa ieri alle 14:00.'
  );
  await expect(page.locator('#announce')).toHaveText('La previsione è vecchia.');
});

test('says when the forecast is missing', async ({ page, context }) => {
  await context.route(`${ACCOUNT}/public/v1/*/forecast.json`, (route) =>
    route.fulfill({ status: 404, headers: { 'access-control-allow-origin': '*' }, body: '' })
  );
  await page.goto('/pedrengo');
  await expect(page.locator('#statusline .bad')).toHaveText(
    'Previsione non disponibile in questo momento.'
  );
});

test('says when the data cannot be fetched', async ({ page, context }) => {
  await context.route(`${ACCOUNT}/public/**`, (route) =>
    route.fulfill({ status: 500, headers: { 'access-control-allow-origin': '*' }, body: '' })
  );
  await page.goto('/pedrengo');
  await expect(page.locator('#statusline .warn')).toHaveText(
    'Non riusciamo a scaricare i dati: riproviamo tra un minuto.'
  );
  await expect(page.locator('#announce')).toHaveText('Non riusciamo a scaricare i dati.');
});

test('says once when the device goes offline, and when it is back', async ({ page, context }) => {
  await page.goto('/pedrengo');
  await expect(page.locator('#statusline')).toHaveText('Emessa alle 14:00, 1 h 10 min fa.');
  await expect(page.locator('#announce')).toHaveText('');
  await context.setOffline(true);
  await page.clock.runFor(10 * 60_000);
  await expect(page.locator('#statusline .warn')).toHaveText(
    'Sei offline: dati scaricati alle 15:10.'
  );
  await expect(page.locator('#announce')).toHaveText('Sei offline.');
  await context.setOffline(false);
  await expect(page.locator('#statusline')).toHaveText('Emessa alle 14:00, 1 h 20 min fa.');
  await expect(page.locator('#announce')).toHaveText('Di nuovo in linea.');
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
