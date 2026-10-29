// The town page from the keyboard: every control in reading order with its
// focus showing, the skip link and the section bar, the 48 ore range read
// aloud hour by hour, and the section bar as the only thing that sticks.
import { expect, test, type Page } from '@playwright/test';
import { openState, TOWNS } from './fixtures.ts';

test.describe.configure({ mode: 'parallel' });

const focused = (page: Page) =>
  page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (!element || element === document.body) return null;
    const style = getComputedStyle(element);
    return {
      name: element.getAttribute('aria-label') ?? element.textContent?.trim() ?? '',
      visible: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0
    };
  });

for (const town of TOWNS) {
  test(`reaches the controls of /${town} in order, focus showing`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await openState(page, 'pioggia', `/${town}`, baseURL ?? '');
    const names: string[] = [];
    for (let i = 0; i < 80; i++) {
      await page.keyboard.press('Tab');
      const now = await focused(page);
      if (!now) break;
      expect(now.visible, `focus on ${now.name}`).toBe(true);
      names.push(now.name);
    }
    const order = [
      'Vai al contenuto',
      'Meteo',
      'Pedrengo',
      'Sesto Calende',
      'Perché una stazione',
      'Adesso',
      '48 ore',
      '10 giorni',
      'Radar',
      'Grafico',
      'Tabella',
      'Ora del grafico',
      'Avvia',
      "Ora dell'immagine",
      'Stato delle fonti'
    ];
    const at = order.map((name) => names.indexOf(name));
    expect(at.every((index) => index >= 0)).toBe(true);
    expect(at).toEqual([...at].sort((a, b) => a - b));
  });

  test(`reads the 48 ore hour of /${town} aloud as it moves`, async ({ page, baseURL }) => {
    await openState(page, 'pioggia', `/${town}`, baseURL ?? '');
    const hour = page.getByRole('slider', { name: 'Ora del grafico' });
    await hour.focus();
    await expect(hour).toHaveAttribute('aria-valuetext', /^sabato 24, 16:00, -?\d+ °C modelli da/);
    await page.keyboard.press('ArrowRight');
    await expect(hour).toHaveAttribute('aria-valuetext', /^sabato 24, 17:00, /);
  });

  test(`labels both 02:00 of the night summer time ends on /${town}`, async ({ page, baseURL }) => {
    await openState(page, 'pioggia', `/${town}`, baseURL ?? '');
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
}

test('skips to the content, then follows the section bar', async ({ page, baseURL }) => {
  await openState(page, 'pioggia', '/pedrengo', baseURL ?? '');
  await page.keyboard.press('Tab');
  expect((await focused(page))?.name).toBe('Vai al contenuto');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main$/);
  await page.keyboard.press('Tab');
  expect((await focused(page))?.name).toBe('Perché una stazione');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  expect((await focused(page))?.name).toBe('48 ore');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#ore-48$/);
  // Clear of the sticky bar, and marked as the section being read.
  const top = await page.locator('#ore-48').evaluate((e) => e.getBoundingClientRect().top);
  expect(top).toBeGreaterThanOrEqual(44);
  expect(top).toBeLessThan(120);
  await expect(page.locator('.sections a[href="#ore-48"]')).toHaveAttribute('aria-current', 'true');
});

test('reaches the radar controls from the 48 ore range on a phone', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await openState(page, 'pioggia', '/pedrengo', baseURL ?? '');
  await page.getByRole('slider', { name: 'Ora del grafico' }).focus();
  const names: string[] = [];
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press('Tab');
    names.push((await focused(page))?.name ?? '');
  }
  expect(names).toContain('Avvia');
  await expect(page.getByRole('button', { name: 'Avvia' })).not.toHaveAttribute(
    'aria-disabled',
    'true'
  );
});

test('plays and stops the radar from the keyboard', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openState(page, 'pioggia', '/sesto-calende', baseURL ?? '');
  await page.getByRole('button', { name: 'Avvia' }).focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('button', { name: 'Ferma' })).toBeFocused();
  await page.keyboard.press('Space');
  await expect(page.getByRole('button', { name: 'Avvia' })).toBeFocused();
});

test('leaves the table header in the table', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openState(page, 'pioggia', '/pedrengo', baseURL ?? '');
  await page.getByRole('button', { name: 'Tabella' }).click();
  const header = page.locator('#ore-48 table.data thead th').first();
  expect(await header.evaluate((th) => getComputedStyle(th).position)).toBe('static');
});

test('sticks nothing below 500 px of height', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 900, height: 480 });
  await openState(page, 'pioggia', '/pedrengo', baseURL ?? '');
  await page.getByRole('button', { name: 'Tabella' }).click();
  const position = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((e) => getComputedStyle(e).position);
  expect(await position('.sections')).toBe('static');
  expect(await position('#ore-48 table.data thead th')).toBe('static');
});
