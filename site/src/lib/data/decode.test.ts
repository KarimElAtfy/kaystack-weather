import { readFileSync } from 'node:fs';
import { describe, expect, test } from 'vitest';
import { DecodeError, decodeForecast, decodeNow, decodeRadar, decodeStatus } from './decode.ts';

const read = (path: string) =>
  JSON.parse(readFileSync(`tests/fixtures/${path}`, 'utf8')) as Record<string, any>;
const SCENARIOS = ['pioggia', 'asciutto', 'vecchi', 'mancanti'];
const TOWNS = ['pedrengo', 'sesto-calende'];

describe('accepts every fixture', () => {
  for (const scenario of SCENARIOS) {
    test(scenario, () => {
      expect(() => decodeStatus(read(`${scenario}/status.json`))).not.toThrow();
      for (const town of TOWNS) {
        expect(decodeNow(read(`${scenario}/v1/${town}/now.json`)).town).toBe(town);
        expect(
          decodeForecast(read(`${scenario}/v1/${town}/forecast.json`)).hourly.time
        ).toHaveLength(49);
        if (scenario !== 'mancanti') {
          expect(decodeRadar(read(`${scenario}/v1/${town}/radar.json`)).frames).toHaveLength(12);
        }
      }
    });
  }
});

test('refuses another major version of a file', () => {
  const now = read('pioggia/v1/pedrengo/now.json');
  now.schema = 'now/2';
  expect(() => decodeNow(now)).toThrow(DecodeError);
});

test('refuses a series shorter than its hours', () => {
  const forecast = read('pioggia/v1/pedrengo/forecast.json');
  forecast.hourly.wind_kmh.mean.pop();
  expect(() => decodeForecast(forecast)).toThrow(
    'forecast.hourly.wind_kmh.mean: 48 values, not 49'
  );
});

test('refuses a required field that is missing', () => {
  const now = read('pioggia/v1/pedrengo/now.json');
  delete now.reference;
  expect(() => decodeNow(now)).toThrow('now.reference: not an object');
});

test('refuses a time that is not UTC', () => {
  const now = read('pioggia/v1/pedrengo/now.json');
  now.metar.observed_at = '2026-10-24T14:50:00+02:00';
  expect(() => decodeNow(now)).toThrow('now.metar.observed_at');
});

test('refuses a sprite that is not a plain file name', () => {
  const radar = read('pioggia/v1/pedrengo/radar.json');
  radar.sprite = '../../status.json';
  expect(() => decodeRadar(radar)).toThrow('radar.sprite');
});

test('refuses a sprite encoding it cannot read', () => {
  const radar = read('pioggia/v1/pedrengo/radar.json');
  radar.encoding = 'colour/1';
  expect(() => decodeRadar(radar)).toThrow('radar.encoding');
});

test('ignores fields it does not know', () => {
  const forecast = read('pioggia/v1/pedrengo/forecast.json');
  forecast.hourly.snow = { n_models: [1] };
  expect(() => decodeForecast(forecast)).not.toThrow();
});

test('takes files without the fields added later in v1', () => {
  const now = decodeNow(read('mancanti/v1/pedrengo/now.json'));
  expect(now.metar?.raw).toBeUndefined();
  expect(
    decodeForecast(read('mancanti/v1/pedrengo/forecast.json')).daily.cloud_pct
  ).toBeUndefined();
});

test('takes a missing block and nulls inside the series', () => {
  const now = decodeNow(read('mancanti/v1/sesto-calende/now.json'));
  expect(now.radar).toBeNull();
  expect(now.metar?.dew_point_c).toBeNull();
  const forecast = decodeForecast(read('mancanti/v1/pedrengo/forecast.json'));
  expect(forecast.hourly.temperature_c.mean[30]).toBeNull();
});
