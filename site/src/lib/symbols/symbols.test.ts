import { expect, test } from 'vitest';
import { has } from '#lib/copy/t.ts';
import { fromCover, fromMetar, pick } from './pick.ts';
import { ICON_IDS, SYMBOL_IDS, favicon, sprite } from './sprite.ts';

test('draws every symbol a pick can ask for', () => {
  const asked = new Set<string>();
  for (const cloud of [null, 5, 30, 70, 95]) {
    for (const [n, m, mm] of [
      [0, 10, 0],
      [3, 10, 0.2],
      [6, 10, 0.5],
      [8, 10, 2],
      [10, 10, 9]
    ] as const) {
      for (const night of [false, true]) {
        const sky = pick(cloud, n, m, mm, night, false);
        asked.add(sky.base);
        if (sky.drops) asked.add(sky.drops);
        expect(has(`sky.${sky.key}`)).toBe(true);
      }
    }
  }
  for (const code of ['-RA BR', '+TSRA', 'SN', 'FG', 'CAVOK', 'FEW', 'BKN', 'OVC']) {
    const sky = fromMetar(code) ?? fromCover(code, true);
    if (sky) asked.add(sky.base);
    if (sky?.drops) asked.add(sky.drops);
  }
  expect([...asked].filter((id) => !SYMBOL_IDS.includes(id))).toEqual([]);
});

test('calls rain possible from a fifth of the models and drawn from half', () => {
  expect(pick(10, 2, 10, 0.1, false, false)).toMatchObject({
    drops: 'drops-maybe',
    key: 'rain_maybe'
  });
  expect(pick(10, 5, 10, 0.5, false, false)).toMatchObject({
    base: 'few-day-wet',
    drops: 'drops-1',
    key: 'rain_1'
  });
  expect(pick(95, 10, 10, 25, false, true)).toMatchObject({ drops: 'drops-3', key: 'rain_3' });
  expect(pick(10, 1, 10, 0, true, false)).toMatchObject({
    base: 'clear-night',
    key: 'clear_night'
  });
});

test('reads the METAR weather before its cloud cover', () => {
  expect(fromMetar('-RA BR')).toMatchObject({ drops: 'drops-1' });
  expect(fromMetar('BR')).toBeNull();
  expect(fromCover('SCT', false)).toMatchObject({ base: 'few-day' });
});

test('writes one symbol per id with the page tokens as colours', () => {
  const svg = sprite();
  for (const id of [...SYMBOL_IDS, ...ICON_IDS.map((i) => `i-${i}`)]) {
    expect(svg).toContain(`<symbol id="${id}"`);
  }
  expect(svg).toContain('var(--sym-sun');
  expect(svg).not.toContain('style="');
});

test('draws a favicon that needs no page tokens', () => {
  expect(favicon()).toContain('var(--sym-sun,#e9a10b)');
  expect(favicon()).toContain('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">');
});
