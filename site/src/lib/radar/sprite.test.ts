import { readFileSync } from 'node:fs';
import { inflateSync } from 'node:zlib';
import { expect, test } from 'vitest';
import { SCALE, aroundTown, framesFrom, indexOf, paint, rgba } from './sprite.ts';

const grey = (index: number) => Math.round((255 * (index + 0.5)) / 9);

test('reads every index back from its grey', () => {
  for (let i = 1; i <= 8; i++) expect(indexOf(grey(i), 255)).toBe(i);
  expect(indexOf(grey(3), 0)).toBe(0);
});

// The fixture sprite is a grey plus alpha PNG; this unpacks it to RGBA the way
// a browser does, for filter type 0 rows, which is what the fixtures use.
function unpack(file: string) {
  const png = readFileSync(file);
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  const chunks: Buffer[] = [];
  for (let at = 8; at < png.length;) {
    const length = png.readUInt32BE(at);
    if (png.toString('ascii', at + 4, at + 8) === 'IDAT')
      chunks.push(png.subarray(at + 8, at + 8 + length));
    at += length + 12;
  }
  const rows = inflateSync(Buffer.concat(chunks));
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const g = rows[y * (width * 2 + 1) + 1 + x * 2] ?? 0;
      const a = rows[y * (width * 2 + 1) + 2 + x * 2] ?? 0;
      rgba.set([g, g, g, a], (y * width + x) * 4);
    }
  }
  return { width, rgba };
}

test('splits the sprite into frames and finds the rain the pipeline saw at the town', () => {
  const radar = JSON.parse(
    readFileSync('tests/fixtures/pioggia/v1/sesto-calende/radar.json', 'utf8')
  );
  const { width, rgba } = unpack(`tests/fixtures/pioggia/v1/sesto-calende/${radar.sprite}`);
  const frames = framesFrom(rgba, width, { width: 120, height: 120, columns: 4 }, 12);
  expect(frames).toHaveLength(12);
  const last = frames.at(-1)!;
  const { here, near } = aroundTown(last, 120, radar.town_px, 1);
  const now = JSON.parse(readFileSync('tests/fixtures/pioggia/v1/sesto-calende/now.json', 'utf8'));
  const classOf = (rate: number) => [0.2, 1, 2, 6, 15, 40].filter((b) => rate >= b).length;
  expect(here).toBe(classOf(now.radar.rate_mm_h));
  expect(near).toBe(classOf(now.radar.max_10km_mm_h));
});

test('treats a missing frame as no data everywhere', () => {
  const radar = JSON.parse(readFileSync('tests/fixtures/vecchi/v1/pedrengo/radar.json', 'utf8'));
  const { width, rgba } = unpack(`tests/fixtures/vecchi/v1/pedrengo/${radar.sprite}`);
  const frames = framesFrom(rgba, width, { width: 120, height: 120, columns: 4 }, 12);
  expect(aroundTown(frames[7]!, 120, radar.town_px, 1)).toEqual({ here: -1, near: 0 });
});

const PALETTE = [
  [0, 0, 0, 0],
  [1, 1, 1, 255],
  [9, 9, 9, 255],
  [],
  [],
  [],
  [],
  [5, 5, 5, 140],
  [5, 5, 5, 40]
] as never;
const at = (target: Uint8ClampedArray, wide: number, x: number, y: number) => [
  ...target.slice((y * wide + x) * 4, (y * wide + x) * 4 + 4)
];

test('paints rain in the palette and leaves dry cells clear', () => {
  const wide = 3 * SCALE;
  const target = new Uint8ClampedArray(wide * SCALE * 4);
  paint(Uint8Array.from([0, 2, 0]), PALETTE, target, 3);
  expect(at(target, wide, 1, 1)).toEqual([0, 0, 0, 0]);
  expect(at(target, wide, SCALE + 1, 1)).toEqual([9, 9, 9, 255]);
});

test('draws no data as thin diagonal lines, not whole cells', () => {
  const wide = 3 * SCALE;
  const target = new Uint8ClampedArray(wide * 3 * SCALE * 4);
  paint(Uint8Array.from([7, 8, 8, 8, 8, 7, 8, 7, 8]), PALETTE, target, 3);
  const lined = (x: number, y: number) => at(target, wide, x, y)[3] === 140;
  expect(lined(0, 0)).toBe(true);
  expect(lined(1, 0)).toBe(true);
  expect(lined(2, 0)).toBe(false);
  expect(lined(5, 7)).toBe(true);
  expect(lined(4, 4)).toBe(false);
});

test('reads colours as the browser computes them', () => {
  expect(rgba('#2a6fd0')).toEqual([42, 111, 208, 255]);
  expect(rgba('rgba(70, 78, 90, 0.55)')).toEqual([70, 78, 90, 140]);
  expect(rgba('rgb(31 79 134)')).toEqual([31, 79, 134, 255]);
});
