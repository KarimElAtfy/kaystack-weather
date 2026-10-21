import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { DATA, forecastFile, nowFile, radarFile, statusFile } from './source.ts';

const read = (path: string): unknown => JSON.parse(readFileSync(`tests/fixtures/${path}`, 'utf8'));
const at = (stamp: string) => Date.parse(stamp);

test('asks the dev server while testing and the public account in a build', () => {
  expect(DATA).toBe('/data');
  expect(nowFile('pedrengo').url).toBe('/data/v1/pedrengo/now.json');
  expect(statusFile().url).toBe('/data/status.json');
});

test('expects the next radar frame before the next METAR', () => {
  const source = nowFile('pedrengo');
  const now = source.decode(read('pioggia/v1/pedrengo/now.json'));
  expect(source.due(now)).toBe(at('2026-10-24T13:05:00Z') + 7 * 60_000);
});

test('falls back on the METAR when the radar block is missing', () => {
  const source = nowFile('pedrengo');
  const now = source.decode(read('mancanti/v1/pedrengo/now.json'));
  expect(source.due(now)).toBe(at('2026-10-24T12:50:00Z') + 37 * 60_000);
});

test('expects a new forecast an hour after the last one was written', () => {
  const source = forecastFile('sesto-calende');
  const forecast = source.decode(read('pioggia/v1/sesto-calende/forecast.json'));
  expect(source.due(forecast)).toBe(at('2026-10-24T12:04:00Z') + 63 * 60_000);
});

test('expects new radar frames from the last one', () => {
  const source = radarFile('pedrengo');
  const radar = source.decode(read('vecchi/v1/pedrengo/radar.json'));
  expect(source.due(radar)).toBe(at('2026-10-24T12:20:00Z') + 7 * 60_000);
});

test('reads the sources list only on request', () => {
  expect(statusFile().lazy).toBe(true);
});
