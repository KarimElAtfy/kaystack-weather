import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { decodeForecast } from '#lib/data/decode.ts';
import { daysShown } from './d10.ts';

const daily = (scenario: string) =>
  decodeForecast(
    JSON.parse(readFileSync(`tests/fixtures/${scenario}/v1/pedrengo/forecast.json`, 'utf8'))
  ).daily;

test('leaves out a day no model reaches', () => {
  expect(daysShown(daily('pioggia'))).toHaveLength(10);
  expect(daysShown(daily('mancanti'))).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
});
