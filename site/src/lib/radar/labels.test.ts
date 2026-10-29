import { expect, test } from 'vitest';
import { place, type Name } from './labels.ts';

const town: Name = { key: 'town', x: 100, y: 100, w: 60, h: 14 };
const ring = (km: number): Name => ({ key: `ring ${km}`, x: 100, y: 100 - km * 1.5, w: 34, h: 14 });

test('names the town beside its marker, on the left at the right edge', () => {
  expect(place(200, 200, [], town, [], []).get('town')).toEqual({ left: 108, top: 93 });
  const edge = { ...town, x: 180 };
  expect(place(200, 200, [], edge, [], []).get('town')!.left).toBe(180 - 6 - 2 - 60);
});

test('keeps the town even when nothing else fits', () => {
  const placed = place(80, 40, [], { ...town, x: 40, y: 20 }, [ring(10)], []);
  expect([...placed.keys()]).toEqual(['town']);
});

test('drops a city before a ring distance, and the town never', () => {
  const city: Name = { key: 'Bergamo', x: 100, y: 84, w: 60, h: 14 };
  const placed = place(200, 200, [], town, [ring(10)], [city]);
  expect(placed.has('ring 10')).toBe(true);
  expect(placed.has('Bergamo')).toBe(false);
});

test('moves a city to the first side where its name fits', () => {
  const city: Name = { key: 'Lecco', x: 190, y: 40, w: 40, h: 14 };
  expect(place(200, 200, [], town, [], [city]).get('Lecco')).toEqual({
    left: 190 - 3 - 2 - 40,
    top: 33
  });
});

test('leaves a city off when its dot sits on something kept', () => {
  const city: Name = { key: 'Qui', x: 101, y: 101, w: 20, h: 14 };
  expect(place(200, 200, [], town, [], [city]).has('Qui')).toBe(false);
});

test('moves the town under its marker when neither side has room', () => {
  const wide = { ...town, x: 80, w: 90 };
  expect(place(160, 200, [], wide, [], []).get('town')).toEqual({ left: 35, top: 108 });
});
