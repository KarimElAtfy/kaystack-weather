// The 48-hour chart's geometry: how tall each lane is, how often a label fits.
// Text sizes come from the page (they follow the user's text setting), so every
// decision here starts from the measured font, never from a fixed pixel size.

export type Lane =
  | 'day'
  | 'sky'
  | 'temp'
  | 'rainTitle'
  | 'rain'
  | 'windTitle'
  | 'arrows'
  | 'wind'
  | 'axis'
  | 'models';
export type Rows = Partial<Record<Lane, [number, number]>> & { height: number };

// The temperature plot's height on a narrow and a wide chart, and its floor
// when the chart has to fit under the screen's cap.
const PLOT_NARROW = 140;
const PLOT_WIDE = 190;
export const PLOT_MIN = 96;
export const NARROW = 560;

// Lanes from top to bottom. Under a cap the sky goes first, then the wind
// arrows, then the plot shortens.
export function rows(width: number, font: number, cap: number | null): Rows {
  const line = Math.ceil(font * 1.4);
  const narrow = width < NARROW;
  const icon = symbolSize(font);
  const heights: [Lane, number][] = [
    ['day', line + 2],
    ['sky', icon + 6],
    ['temp', narrow ? PLOT_NARROW : PLOT_WIDE],
    ['rainTitle', line + 6],
    ['rain', narrow ? 28 : 36],
    ['windTitle', line + 6],
    ['arrows', 14],
    ['wind', line],
    ['axis', line + 6],
    ['models', 10]
  ];
  const total = () => heights.reduce((sum, [, h]) => sum + h, 0);
  const drop = (lane: Lane) =>
    heights.splice(
      heights.findIndex(([name]) => name === lane),
      1
    );
  if (cap !== null && total() > cap) drop('sky');
  if (cap !== null && total() > cap) drop('arrows');
  if (cap !== null && total() > cap) {
    const plot = heights.find(([name]) => name === 'temp')!;
    plot[1] = Math.max(PLOT_MIN, plot[1] - (total() - cap));
  }
  const out: Rows = { height: 0 };
  for (const [lane, h] of heights) {
    out[lane] = [out.height, out.height + h];
    out.height += h;
  }
  return out;
}

export const symbolSize = (font: number) => Math.max(20, Math.round(font * 1.8));

// The shortest step, in hours, at which a label of `widest` pixels and its gap
// fit between neighbours. Steps divide the day, so labels fall on round hours.
export function every(perHour: number, widest: number, gap = 8): number {
  return [1, 2, 3, 6, 12, 24].find((step) => perHour * step >= widest + gap) ?? 24;
}

// The longest of the texts that fits in `room`, or null.
export function longest(texts: string[], room: number, measure: (text: string) => number) {
  return texts.find((text) => measure(text) + 8 <= room) ?? null;
}

// Labels that would overlap are dropped, keeping the earlier ones in `order`.
export type Box = { left: number; right: number; top: number; bottom: number };
export const overlap = (a: Box, b: Box) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

export function keep<T extends { box: Box }>(order: T[]): T[] {
  const kept: T[] = [];
  for (const item of order)
    if (!kept.some((other) => overlap(other.box, item.box))) kept.push(item);
  return kept;
}
