import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast } from '#lib/data/decode.ts';
import { daysShown, rawNote } from './d10.ts';

const daily = (scenario: string) =>
  decodeForecast(
    JSON.parse(readFileSync(`tests/fixtures/${scenario}/v1/pedrengo/forecast.json`, 'utf8'))
  ).daily;

test('leaves out a day no model reaches', () => {
  expect(daysShown(daily('pioggia'))).toHaveLength(10);
  expect(daysShown(daily('mancanti'))).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
});

test('names which of minimum and maximum went without the correction', () => {
  const d = daily('pioggia');
  const raw = { ...d.tmin_c, corrected: false };
  expect(rawNote(d)).toBe(null);
  expect(rawNote({ ...d, tmin_c: raw })).toBe('d10.note_raw_min');
  expect(rawNote({ ...d, tmax_c: { ...d.tmax_c, corrected: false } })).toBe('d10.note_raw_max');
  expect(rawNote(daily('non-corretto'))).toBe('d10.note_raw');
});
