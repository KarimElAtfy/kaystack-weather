import { expect, test } from 'vitest';
import { distance, towns } from './towns.ts';

test('reads both towns from the town files', () => {
  expect(towns().map((town) => town.slug)).toEqual(['pedrengo', 'sesto-calende']);
});

test('measures the station distance the way the contract does', () => {
  const [pedrengo, sesto] = towns();
  expect(pedrengo).toMatchObject({ station: 'Torre Boldone', km: 3.4 });
  expect(sesto).toMatchObject({ station: 'Ispra JRC', km: 9.1 });
  expect(distance({ lat: 45, lon: 9 }, { lat: 46, lon: 9 })).toBe(111.2);
});
