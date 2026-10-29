import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast } from '#lib/data/decode.ts';
import { hm } from '#lib/time.ts';
import { strip, verdict } from './ahead.ts';

const read = (path: string) => decodeForecast(JSON.parse(readFileSync(path, 'utf8')));
// The public file as published on 28 October 2026 at 21:45 in Rome.
const recorded = read('src/lib/chart/recorded/pedrengo-2026-10-28.json');
const fixture = (scenario: string) => read(`tests/fixtures/${scenario}/v1/pedrengo/forecast.json`);
const EVENING = Date.parse('2026-10-28T21:29:00Z');
const NOON = Date.parse('2026-10-24T13:10:00Z');
const PEDRENGO = [45.7, 9.73] as const;

const cells = (forecast: typeof recorded, now: number) =>
  strip(forecast.hourly, now, ...PEDRENGO).map(
    (c) => `${hm(c.time)} ${c.sky.key} ${c.temp} ${c.rainy}/${c.counted}`
  );

test('says none of the models gives rain when none does', () => {
  expect(verdict(recorded.hourly, EVENING)).toBe(
    'Nessuno dei 10 modelli dà pioggia nelle prossime 12 ore.'
  );
});

test('names the first hour most models give rain', () => {
  expect(verdict(fixture('pioggia').hourly, NOON)).toBe('Pioggia dalle 17:00 per 5 modelli su 10.');
});

// The old sentence went quiet under a fifth of the models; this one would then
// say that none of them gives rain.
test('names a single model too', () => {
  const hourly = structuredClone(recorded.hourly);
  const four = hourly.time.findIndex((time) => time === '2026-10-29T03:00:00Z');
  hourly.rain.n_models[four] = 1;
  expect(verdict(hourly, EVENING)).toBe('Pioggia domani dalle 03:00 solo per 1 modello su 10.');
});

test('draws six cells two hours apart from the next full hour', () => {
  expect(cells(recorded, EVENING)).toEqual([
    '23:00 few_night 11.5 0/10',
    '01:00 few_night 10.8 0/10',
    '03:00 few_night 10.7 0/10',
    '05:00 few_night 10.5 0/10',
    '07:00 few_day 10.1 0/10',
    '09:00 few_day 13.3 0/10'
  ]);
  expect(cells(fixture('pioggia'), NOON)).toEqual([
    '16:00 rain_1 15.9 5/10',
    '18:00 rain_2 14.8 8/10',
    '20:00 rain_2 12.6 10/10',
    '22:00 rain_2 9.6 10/10',
    '00:00 rain_2 7.6 6/10',
    '02:00 rain_maybe 8.3 3/10'
  ]);
});
