import { expect, test } from 'vitest';
import { PLOT_MIN, every, keep, longest, rows } from './meteogram.ts';

test('stacks every lane when the screen has room', () => {
  const r = rows(343, 13, 600);
  expect(r.sky).toBeDefined();
  expect(r.arrows).toBeDefined();
  expect(r.temp![1] - r.temp![0]).toBe(140);
  expect(r.height).toBeLessThanOrEqual(600);
});

test('gives up the sky, then the arrows, then plot height under the cap', () => {
  const full = rows(800, 13, null).height;
  expect(rows(800, 13, full - 10).sky).toBeUndefined();
  expect(rows(800, 13, full - 10).arrows).toBeDefined();
  const tight = rows(800, 13, 260);
  expect(tight.sky).toBeUndefined();
  expect(tight.arrows).toBeUndefined();
  expect(tight.temp![1] - tight.temp![0]).toBeGreaterThanOrEqual(PLOT_MIN);
});

test('grows the text lanes with the text, never the plot', () => {
  const normal = rows(343, 13, null);
  const large = rows(343, 26, null);
  expect(large.axis![1] - large.axis![0]).toBeGreaterThan(normal.axis![1] - normal.axis![0]);
  expect(large.temp![1] - large.temp![0]).toBe(normal.temp![1] - normal.temp![0]);
});

test('spaces labels by their measured width', () => {
  expect(every(28.5, 15)).toBe(1);
  expect(every(7, 15)).toBe(6);
  expect(every(7, 30)).toBe(6);
  expect(every(4.6, 30)).toBe(12);
});

test('picks the longest day name that fits', () => {
  const width = (text: string) => text.length * 7;
  expect(longest(['domenica 25', 'dom 25', 'dom'], 100, width)).toBe('domenica 25');
  expect(longest(['domenica 25', 'dom 25', 'dom'], 50, width)).toBe('dom 25');
  expect(longest(['domenica 25', 'dom 25', 'dom'], 20, width)).toBeNull();
});

test('keeps the earlier of two labels that overlap', () => {
  const at = (left: number) => ({ box: { left, right: left + 30, top: 0, bottom: 10 } });
  expect(keep([at(0), at(20), at(40)]).map((l) => l.box.left)).toEqual([0, 40]);
});
