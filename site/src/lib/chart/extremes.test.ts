import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast } from '#lib/data/decode.ts';
import { hour } from '#lib/time.ts';
import { labels, pair, today, tonight, type Reading } from './extremes.ts';

const read = (path: string) => decodeForecast(JSON.parse(readFileSync(path, 'utf8')));
// The public file as published on 28 October 2026 at 21:45 in Rome.
const recorded = read('src/lib/chart/recorded/pedrengo-2026-10-28.json');
const fixture = (scenario: string) => read(`tests/fixtures/${scenario}/v1/pedrengo/forecast.json`);

const at = (forecast: typeof recorded, reading: Reading | null) =>
  reading && `${reading.value} alle ${hour(Date.parse(forecast.hourly.time[reading.i]!))}`;
const drawn = (forecast: typeof recorded, now: string) =>
  labels(forecast.hourly, Date.parse(now)).map((l) => `${l.kind} ${at(forecast, l)}`);

test('labels the line with its own values, not the daily ones', () => {
  expect(drawn(recorded, '2026-10-28T21:29:00Z')).toEqual([
    'low 10.1 alle 07',
    'high 18 alle 13',
    'low 10.3 alle 06'
  ]);
  expect(recorded.daily.tmax_c.mean[0]).toBe(18.5);
});

test('reads stanotte and domani from 15:00, oggi and stanotte before', () => {
  expect(pair(recorded, Date.parse('2026-10-28T21:29:00Z'))).toEqual([
    { word: 'tonight', value: 10.1 },
    { word: 'tomorrow', value: 18.5 }
  ]);
  const morning = fixture('pioggia');
  expect(pair(morning, Date.parse('2026-10-24T12:10:00Z'))).toEqual([
    { word: 'today', value: 16 },
    { word: 'tonight', value: 7.6 }
  ]);
});

test('gives the chart the same stanotte as the pair', () => {
  const now = Date.parse('2026-10-28T21:29:00Z');
  const low = tonight(recorded.hourly, now);
  expect(labels(recorded.hourly, now)).toContainEqual({ ...low, kind: 'low' });
});

test('keeps the night under way until 06:00, then turns to the next one', () => {
  expect(at(recorded, tonight(recorded.hourly, Date.parse('2026-10-29T03:30:00Z')))).toBe(
    '10.1 alle 07'
  );
  expect(at(recorded, tonight(recorded.hourly, Date.parse('2026-10-29T06:30:00Z')))).toBe(
    '10.3 alle 06'
  );
});

test('leaves out the rest of a night already started in the morning', () => {
  expect(drawn(recorded, '2026-10-29T06:30:00Z')).toEqual(['high 18 alle 13', 'low 10.3 alle 06']);
});

test('counts the night the clocks go back with its repeated hour', () => {
  const night = fixture('pioggia');
  expect(at(night, tonight(night.hourly, Date.parse('2026-10-24T12:10:00Z')))).toBe('7.6 alle 00');
});

test('shows no figure for a window with an hour the correction missed', () => {
  const gaps = fixture('mancanti');
  const now = Date.parse('2026-10-24T12:10:00Z');
  expect(labels(gaps.hourly, now).map((l) => l.kind)).toEqual(['high', 'low']);
  const evening = Date.parse('2026-10-25T16:10:00Z');
  expect(tonight(gaps.hourly, evening)).toBeNull();
  expect(pair(gaps, evening)[0]).toEqual({ word: 'tonight', value: null });
});

test('has no oggi once the file holds no hour of today', () => {
  expect(today(recorded.hourly, Date.parse('2026-10-31T10:00:00Z'))).toBeNull();
});
