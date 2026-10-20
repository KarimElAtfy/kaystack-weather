// The rain rate classes. v1 of the contract writes these six in radar.json;
// Adesso uses them before that file has arrived, and radar.json's own bins
// once it has.
import { has, t } from '#lib/copy/t.ts';
import { dec } from '#lib/format.ts';

export type Bin = { index: number; from_mm_h: number; to_mm_h: number | null };

const BOUNDS = [0.2, 1, 2, 6, 15, 40];
export const V1_SCALE: Bin[] = BOUNDS.map((from, i) => ({
  index: i + 1,
  from_mm_h: from,
  to_mm_h: BOUNDS[i + 1] ?? null
}));

// 0 for no rain, else the index of the highest class the rate reaches.
export const classOf = (rate: number, scale: Bin[] = V1_SCALE) =>
  scale.reduce((found, bin) => (rate >= bin.from_mm_h ? bin.index : found), 0);

export function className(index: number): string {
  const key = `radar.class.${index}`;
  return has(key) ? t(key) : '';
}

const bound = (x: number) => dec(x).replace(/,0$/, '');

// "2-6" or "oltre 40", the radar legend's way of writing a range.
export function range(bin: Bin): string {
  if (bin.to_mm_h === null) return t('radar.over', { v: bound(bin.from_mm_h) });
  return `${bound(bin.from_mm_h)}-${bound(bin.to_mm_h)}`;
}
