import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast, decodeNow } from '#lib/data/decode.ts';
import { firstShown, lastFullHour, observed, summary } from './h48.ts';

const forecast = (scenario: string) =>
  decodeForecast(
    JSON.parse(readFileSync(`tests/fixtures/${scenario}/v1/pedrengo/forecast.json`, 'utf8'))
  );
const NOW = Date.parse('2026-10-24T13:10:00Z');

test('trims the hours already gone', () => {
  const times = forecast('pioggia').hourly.time.map(Date.parse);
  expect(new Date(times[firstShown(times, NOW)]!).toISOString()).toBe('2026-10-24T13:00:00.000Z');
});

test('says when most models give rain, by the hour it starts', () => {
  const s = summary(forecast('pioggia').hourly, NOW);
  expect(s.rain).toBe('Pioggia per la maggior parte dei modelli dalle 17:00.');
  expect(s.temp).toMatch(/^Nelle prossime 48 ore la temperatura va da -?\d+ °C a \d+ °C\.$/);
});

test('never says the models are right about now', () => {
  const s = summary(forecast('pioggia').hourly, Date.parse('2026-10-24T15:10:00Z'));
  expect(s.rain).toBe('Pioggia per la maggior parte dei modelli entro le 18:00.');
  expect(s.now).toBe('');
});

test('lets a fresh radar say what is happening now, before the models', () => {
  const radar = decodeNow(
    JSON.parse(readFileSync('tests/fixtures/pioggia/v1/pedrengo/now.json', 'utf8'))
  ).radar!;
  const at = Date.parse(radar.frame_time);
  expect(observed({ ...radar, rate_mm_h: 0 }, at)).toBe('dry');
  expect(observed({ ...radar, rate_mm_h: 0.2 }, at)).toBe('rain');
  expect(observed({ ...radar, rate_mm_h: 3 }, at + 16 * 60_000)).toBe(null);
  expect(observed({ ...radar, no_data: true, rate_mm_h: null }, at)).toBe(null);
  expect(observed(null, at)).toBe(null);
  expect(summary(forecast('asciutto').hourly, NOW, 'dry').now).toBe('Adesso non piove sul paese.');
  expect(summary(forecast('pioggia').hourly, NOW, 'rain').now).toBe('Adesso piove sul paese.');
});

test('says no model gives rain on a dry day', () => {
  expect(summary(forecast('asciutto').hourly, NOW).rain).toBe(
    'Nessun modello dà pioggia nelle prossime 12 ore.'
  );
});

test('finds the last hour with every model', () => {
  const hourly = forecast('pioggia').hourly;
  expect(hourly.temperature_c.m_models[lastFullHour(hourly)]).toBe(10);
  expect(hourly.temperature_c.m_models[lastFullHour(hourly) + 1]).toBe(9);
});
