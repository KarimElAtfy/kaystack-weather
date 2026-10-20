import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast, decodeNow, decodeStatus } from './decode.ts';
import {
  forecastFreshness,
  metarFreshness,
  radarAtTownFreshness,
  radarMapFreshness,
  sourceState
} from './states.ts';

const read = (path: string): unknown => JSON.parse(readFileSync(`tests/fixtures/${path}`, 'utf8'));
const NOW = Date.parse('2026-10-24T13:10:00Z');
const MIN = 60_000;

test('calls a 20-minute METAR fresh and a 170-minute one stale', () => {
  expect(metarFreshness(decodeNow(read('pioggia/v1/pedrengo/now.json')).metar!, NOW)).toBe('fresh');
  expect(metarFreshness(decodeNow(read('vecchi/v1/pedrengo/now.json')).metar!, NOW)).toBe('stale');
  expect(
    metarFreshness(decodeNow(read('vecchi/v1/pedrengo/now.json')).metar!, NOW + 11 * MIN)
  ).toBe('expired');
});

test('gives the radar at the town 15 minutes, then an hour in the past tense', () => {
  const radar = decodeNow(read('vecchi/v1/pedrengo/now.json')).radar!;
  expect(radarAtTownFreshness(radar, Date.parse(radar.frame_time) + 15 * MIN)).toBe('fresh');
  expect(radarAtTownFreshness(radar, NOW)).toBe('stale');
  expect(radarAtTownFreshness(radar, Date.parse(radar.frame_time) + 61 * MIN)).toBe('expired');
});

test('keeps the radar map for three hours after its last frame', () => {
  expect(radarMapFreshness('2026-10-24T12:20:00Z', 15, NOW)).toBe('stale');
  expect(radarMapFreshness('2026-10-24T10:09:00Z', 15, NOW)).toBe('expired');
});

test('judges the forecast by the limits it carries', () => {
  expect(forecastFreshness(decodeForecast(read('pioggia/v1/pedrengo/forecast.json')), NOW)).toBe(
    'fresh'
  );
  const old = decodeForecast(read('vecchi/v1/pedrengo/forecast.json'));
  expect(forecastFreshness(old, NOW)).toBe('stale');
  expect(forecastFreshness(old, NOW + 24 * 60 * MIN)).toBe('expired');
});

test('tells a late source from one the pipeline cannot reach', () => {
  const fresh = decodeStatus(read('pioggia/status.json')).sources;
  expect(sourceState('radar', fresh.radar!, NOW)).toBe('ok');
  expect(sourceState('arpa', fresh.arpa!, NOW)).toBe('ok');
  const old = decodeStatus(read('vecchi/status.json')).sources;
  expect(sourceState('radar', old.radar!, NOW)).toBe('down');
  expect(sourceState('open-meteo', old['open-meteo']!, NOW)).toBe('down');
  expect(sourceState('metar', old.metar!, NOW)).toBe('late');
});
