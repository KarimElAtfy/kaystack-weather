// Where the map's names go, in the map's own pixels at its drawn size. The
// names are page text, so their size follows the reader's settings, and the
// ones that collide give way: other towns first, then the ring distances.
// The town itself is never dropped.

export type Box = { left: number; top: number; right: number; bottom: number };
export type Spot = { left: number; top: number };
// A name to place: its anchor point in map pixels and its measured size.
export type Name = { key: string; x: number; y: number; w: number; h: number };

const meets = (a: Box, b: Box) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
const box = (left: number, top: number, w: number, h: number): Box => ({
  left,
  top,
  right: left + w,
  bottom: top + h
});

// The gap between a point and its name, and the half-size of a city's dot.
const GAP = 4;
const DOT = 3;

export function place(
  width: number,
  height: number,
  taken: Box[],
  town: Name,
  rings: Name[],
  cities: Name[]
): Map<string, Spot> {
  const out = new Map<string, Spot>();
  const used = [...taken];
  const inside = (b: Box) => b.left >= 0 && b.top >= 0 && b.right <= width && b.bottom <= height;
  const free = (b: Box) => inside(b) && !used.some((other) => meets(other, b));
  const keep = (key: string, b: Box) => {
    used.push(b);
    out.set(key, { left: b.left, top: b.top });
  };

  // The town: right of its marker, else left, else under it moved inside the
  // map; kept even where it overlaps something.
  const marker = box(town.x - 2 * DOT, town.y - 2 * DOT, 4 * DOT, 4 * DOT);
  used.push(marker);
  const centred = Math.min(Math.max(0, town.x - town.w / 2), width - town.w);
  const spots = [
    box(town.x + 2 * DOT + GAP / 2, town.y - town.h / 2, town.w, town.h),
    box(town.x - 2 * DOT - GAP / 2 - town.w, town.y - town.h / 2, town.w, town.h),
    box(centred, town.y + 2 * DOT + GAP / 2, town.w, town.h)
  ];
  keep(town.key, spots.find(inside) ?? spots[2]!);

  for (const ring of rings) {
    const b = box(ring.x - ring.w / 2, ring.y - ring.h - 1, ring.w, ring.h);
    if (free(b)) keep(ring.key, b);
  }

  for (const city of cities) {
    const dot = box(city.x - DOT, city.y - DOT, 2 * DOT, 2 * DOT);
    if (!free(dot)) continue;
    const { x, y, w, h } = city;
    const spots = [
      box(x + DOT + GAP / 2, y - h / 2, w, h),
      box(x - DOT - GAP / 2 - w, y - h / 2, w, h),
      box(x - w / 2, y - DOT - h, w, h),
      box(x - w / 2, y + DOT, w, h)
    ];
    const spot = spots.find(free);
    if (!spot) continue;
    used.push(dot);
    keep(city.key, spot);
  }
  return out;
}
