import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { BANNED, parse, visible } from './parse.ts';
import { fill, has, t } from './t.ts';

const { short, long } = parse(readFileSync('src/lib/copy/it.md', 'utf8'));

test('reads every table row and every long text', () => {
  expect(short.length).toBeGreaterThan(250);
  expect(short.find((entry) => entry.key === 'site.name')).toEqual({
    key: 'site.name',
    max: 16,
    text: 'Meteo'
  });
  expect(short.find((entry) => entry.key === 'state.loading')?.max).toBe(30);
  expect(long.find((entry) => entry.key === 'page.how.h_far')?.text).toBe('Giorni 8, 9 e 10');
});

test('keeps the fixed words of every string within its max', () => {
  const over = short.filter((entry) => entry.max !== null && visible(entry.text) > entry.max);
  expect(visible('da {min} a {max}')).toBe(6);
  expect(over).toEqual([]);
});

test('holds none of the characters the hooks refuse', () => {
  expect([...short, ...long].filter((entry) => BANNED.test(entry.text))).toEqual([]);
  expect(BANNED.test('l\u2019ora')).toBe(true);
  expect(BANNED.test('13 °C, città, perché')).toBe(false);
});

test('writes placeholders as single words in braces', () => {
  const broken = short.filter((entry) => /\{(?!\w+\})|(?<!\{\w*)\}/.test(entry.text));
  expect(broken).toEqual([]);
});

test('fills placeholders and leaves unknown ones visible', () => {
  expect(t('models.many', { n: 7, m: 10 })).toBe('7 modelli su 10');
  expect(fill('alle {ora}, {fa}', { ora: '14:50' })).toBe('alle 14:50, {fa}');
});

test('knows which keys exist', () => {
  expect(has('dir.SO')).toBe(true);
  expect(has('dir.SW')).toBe(false);
});
