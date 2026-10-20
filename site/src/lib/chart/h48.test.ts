import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast } from '#lib/data/decode.ts';
import { firstShown, lastFullHour, nextHour, niceStep, summary } from './h48.ts';

const forecast = (scenario: string) =>
  decodeForecast(
    JSON.parse(readFileSync(`tests/fixtures/${scenario}/v1/pedrengo/forecast.json`, 'utf8'))
  );
const NOW = Date.parse('2026-10-24T13:10:00Z');

test('trims the hours already gone and picks the next full hour', () => {
  const times = forecast('pioggia').hourly.time.map(Date.parse);
  expect(new Date(times[firstShown(times, NOW)]!).toISOString()).toBe('2026-10-24T13:00:00.000Z');
  expect(new Date(times[nextHour(times, NOW)]!).toISOString()).toBe('2026-10-24T14:00:00.000Z');
});

test('says when most models give rain, by the hour it starts', () => {
  const s = summary(forecast('pioggia').hourly, NOW);
  expect(s.rain).toBe('Pioggia per la maggior parte dei modelli dalle 17:00.');
  expect(s.temp).toMatch(/^Nelle prossime 48 ore la temperatura va da -?\d+ °C a \d+ °C\.$/);
});

test('says no model gives rain on a dry day', () => {
  expect(summary(forecast('asciutto').hourly, NOW).rain).toBe(
    'Nessun modello dà pioggia nelle prossime 12 ore.'
  );
});

test('rounds axis steps', () => {
  expect(niceStep(12, 4)).toBe(2);
  expect(niceStep(30, 3)).toBe(10);
  expect(niceStep(7, 4)).toBe(2);
});

test('finds the last hour with every model', () => {
  const hourly = forecast('pioggia').hourly;
  expect(hourly.temperature_c.m_models[lastFullHour(hourly)]).toBe(10);
  expect(hourly.temperature_c.m_models[lastFullHour(hourly) + 1]).toBe(9);
});
