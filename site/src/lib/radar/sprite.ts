// The radar sprite holds class indices, not colours (contract radar/1,
// encoding class-grey9/1): grey round(255 (i + 0.5) / 9) for index i, fully
// transparent for 0. These functions turn its pixels into indices per frame,
// read the town and its surroundings from them, and paint a frame in the
// colours of the current theme.

export const NO_RAIN = 0;
export const HATCH_LINE = 7;
export const HATCH_FILL = 8;

export const indexOf = (grey: number, alpha: number) =>
  alpha === 0 ? NO_RAIN : Math.min(HATCH_FILL, Math.floor((grey * 9) / 256));

export type Grid = { width: number; height: number; columns: number };

// pixels: the whole sprite as RGBA, row by row.
export function framesFrom(
  pixels: Uint8ClampedArray,
  spriteWidth: number,
  grid: Grid,
  count: number
): Uint8Array[] {
  return Array.from({ length: count }, (_, k) => {
    const left = (k % grid.columns) * grid.width;
    const top = Math.floor(k / grid.columns) * grid.height;
    const frame = new Uint8Array(grid.width * grid.height);
    for (let y = 0; y < grid.height; y++) {
      for (let x = 0; x < grid.width; x++) {
        const at = ((top + y) * spriteWidth + left + x) * 4;
        frame[y * grid.width + x] = indexOf(pixels[at] ?? 0, pixels[at + 3] ?? 0);
      }
    }
    return frame;
  });
}

const isHatch = (index: number) => index === HATCH_LINE || index === HATCH_FILL;

// The class at the town (-1 where the radar sees nothing) and the highest
// class within 10 km of it.
export function aroundTown(
  frame: Uint8Array,
  width: number,
  town: { x: number; y: number },
  kmPerPx: number
): { here: number; near: number } {
  const value = frame[town.y * width + town.x] ?? NO_RAIN;
  const radius = 10 / kmPerPx;
  let near = 0;
  const height = frame.length / width;
  for (
    let y = Math.max(0, Math.floor(town.y - radius));
    y <= Math.min(height - 1, town.y + radius);
    y++
  ) {
    for (
      let x = Math.max(0, Math.floor(town.x - radius));
      x <= Math.min(width - 1, town.x + radius);
      x++
    ) {
      if ((x - town.x) ** 2 + (y - town.y) ** 2 > radius ** 2) continue;
      const index = frame[y * width + x] ?? NO_RAIN;
      if (!isHatch(index)) near = Math.max(near, index);
    }
  }
  return { here: isHatch(value) ? -1 : value, near };
}

export type Rgba = [number, number, number, number];

// The canvas draws each radar cell as SCALE x SCALE pixels, so that where the
// radar sees nothing the hatch can be thin diagonal lines, as in the legend,
// rather than whole cells in a checker.
export const SCALE = 4;
const PERIOD = 3 * SCALE;
const LINE = 2;

// palette[i] is the colour of index i; index 0 stays transparent. target holds
// (width * SCALE) x (height * SCALE) pixels.
export function paint(
  frame: Uint8Array,
  palette: Rgba[],
  target: Uint8ClampedArray,
  width: number
): void {
  const clear: Rgba = [0, 0, 0, 0];
  const line = palette[HATCH_LINE] ?? clear;
  const wide = width * SCALE;
  frame.forEach((index, i) => {
    const cx = (i % width) * SCALE;
    const cy = Math.floor(i / width) * SCALE;
    const hatch = isHatch(index);
    const colour = index === NO_RAIN || hatch ? clear : (palette[index] ?? clear);
    for (let y = cy; y < cy + SCALE; y++) {
      for (let x = cx; x < cx + SCALE; x++) {
        const own = hatch && (x + y) % PERIOD < LINE ? line : colour;
        target.set(own, (y * wide + x) * 4);
      }
    }
  });
}

// A CSS colour as the page computes it: rgb(...), rgba(...) or #rrggbb.
export function rgba(css: string): Rgba {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(css.trim());
  if (hex) return [parseInt(hex[1]!, 16), parseInt(hex[2]!, 16), parseInt(hex[3]!, 16), 255];
  const parts =
    /rgba?\(([^)]+)\)/
      .exec(css)?.[1]
      ?.split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number) ?? [];
  const [r = 0, g = 0, b = 0, a = 1] = parts;
  return [r, g, b, Math.round(a * 255)];
}
