// The weather symbols and interface icons, drawn as strokes on a 32 x 32 grid and
// written at build time into one sprite that each town page carries in its own
// HTML. symbols.css colours the classes with the page's tokens: WebKit and
// Firefox do not pass the tokens into a sprite read from a file by <use>.
//
// Every sky comes as layers, one per colour: <id>-sun (sun and lightning) and
// <id>-ink (moon, clouds, fog, snow), plus <id> drawing both, so a test can find
// each colour inside the box of the <use> that draws it.

import { inkLayer, sunLayer } from './layers.ts';

// The favicon is drawn by the browser outside the page, so it carries its own
// colours: the light theme's, and the dark theme's for dark tab strips.
const FAVICON_STYLE = `
.y-sun,.y-ink{fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.y-sun{stroke:#b8461b}
.y-ink{stroke:#57534b}
@media (prefers-color-scheme:dark){.y-sun{stroke:#f08b55}.y-ink{stroke:#b3ac9f}}`;

const n = (x: number) => Number(x.toFixed(2));

type Circle = [number, number, number];
// Three bumps whose lower ends rest on one flat base: left, top, right.
type Cloud = [Circle, Circle, Circle];

// The upper of the two points where circles a and b cross.
function cross([ax, ay, ar]: Circle, [bx, by, br]: Circle): [number, number] {
  const d = Math.hypot(bx - ax, by - ay);
  const along = (ar * ar - br * br + d * d) / (2 * d);
  const h = Math.sqrt(ar * ar - along * along);
  const [mx, my] = [ax + (along * (bx - ax)) / d, ay + (along * (by - ay)) / d];
  const [ux, uy] = [(-(by - ay) * h) / d, ((bx - ax) * h) / d];
  return my + uy < my - uy ? [mx + ux, my + uy] : [mx - ux, my - uy];
}

const angle = ([cx, cy]: Circle, [x, y]: [number, number]) => Math.atan2(y - cy, x - cx);

// A clockwise arc on circle c from angle a0 to the point p.
function arc(c: Circle, a0: number, p: [number, number]): string {
  const span = (angle(c, p) - a0 + 4 * Math.PI) % (2 * Math.PI);
  return `A${c[2]} ${c[2]} 0 ${span > Math.PI ? 1 : 0} 1 ${n(p[0])} ${n(p[1])}`;
}

// The outline of a cloud as one path, so no bump shows its hidden half.
function outline([l, t, r]: Cloud): string {
  const base = l[1] + l[2];
  const lt = cross(l, t);
  const tr = cross(t, r);
  return (
    `M${l[0]} ${base} ` +
    arc(l, Math.PI / 2, lt) +
    arc(t, angle(t, lt), tr) +
    arc(r, angle(r, tr), [r[0], base]) +
    'Z'
  );
}

const cloud = (c: Cloud, tint = false) =>
  `<path class="${tint ? 'y-ink y-tint' : 'y-ink'}" d="${outline(c)}"/>`;

const BIG: Cloud = [
  [10, 19.5, 4.5],
  [16.5, 14.5, 7],
  [23, 19.5, 4.5]
];
const SMALL: Cloud = [
  [15.6, 22.2, 3.8],
  [20.8, 18.4, 5.6],
  [25.8, 22.2, 3.8]
];

// A ray is left out where it would run into the cloud beside the sun.
function sun(cx: number, cy: number, r: number, ray: number, beside?: Cloud): string {
  let s = `<circle class="y-sun" cx="${cx}" cy="${cy}" r="${r}"/>`;
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    const [x1, y1] = [cx + Math.cos(a) * (r + 2.4), cy + Math.sin(a) * (r + 2.4)];
    const [x2, y2] = [cx + Math.cos(a) * (r + 2.4 + ray), cy + Math.sin(a) * (r + 2.4 + ray)];
    const hits = beside?.some(([bx, by, br]) => Math.hypot(x2 - bx, y2 - by) < br + 2.2);
    if (!hits) s += `<line class="y-sun" x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}"/>`;
  }
  return s;
}

const moon = (cx: number, cy: number, r: number) =>
  `<path class="y-ink" d="M${n(cx + r * 0.35)} ${n(cy - r)} A${r} ${r} 0 1 0 ${n(cx + r)} ${n(cy + r * 0.45)} A${n(r * 0.8)} ${n(r * 0.8)} 0 0 1 ${n(cx + r * 0.35)} ${n(cy - r)} Z"/>`;

function drop(x: number, y: number, s: number, hollow = false): string {
  const d = `M${x} ${y} C${x} ${y} ${n(x - 2.2 * s)} ${n(y + 2.9 * s)} ${n(x - 2.2 * s)} ${n(y + 4 * s)} A${n(2.2 * s)} ${n(2.2 * s)} 0 0 0 ${n(x + 2.2 * s)} ${n(y + 4 * s)} C${n(x + 2.2 * s)} ${n(y + 2.9 * s)} ${x} ${y} ${x} ${y} Z`;
  return `<path class="${hollow ? 'y-rain-line' : 'y-rain'}" d="${d}"/>`;
}

const flake = (x: number, y: number) =>
  [0, 60, 120]
    .map((deg) => {
      const [dx, dy] = [
        Math.cos((deg * Math.PI) / 180) * 1.9,
        Math.sin((deg * Math.PI) / 180) * 1.9
      ];
      return `<line class="y-ink" x1="${n(x - dx)}" y1="${n(y - dy)}" x2="${n(x + dx)}" y2="${n(y + dy)}"/>`;
    })
    .join('');

const up = (inner: string, dy: number) =>
  inner && dy ? `<g transform="translate(0 ${dy})">${inner}</g>` : inner;

type Layers = { sun?: string; ink?: string };

const BOLT =
  '<path class="y-sun y-bolt" d="M17.4 21.2 L13.6 27 H16.4 L15 31 L19.6 25.2 H16.8 L18.6 21.2 Z"/>';

// A base is the sky without rain; its -wet form sits higher to leave room for drops.
function skies(): Record<string, Layers> {
  // With rain the cloud moves up beside the sun, which stays put so its rays
  // keep inside the box; the rays are then cut against the moved cloud.
  const few = (night: boolean, lift = 0): Layers => {
    const c = SMALL.map(([x, y, r]) => [x, y + lift, r]) as Cloud;
    return night
      ? { ink: moon(10, 10, 5) + cloud(c) }
      : { sun: sun(11, 11, 4, 2.6, c), ink: cloud(c) };
  };
  const overcast = cloud(BIG, true);
  return {
    'clear-day': { sun: sun(16, 16, 5.5, 3.2) },
    'clear-night': { ink: moon(15, 16, 8.5) },
    'few-day': few(false),
    'few-night': few(true),
    cloudy: { ink: up(cloud(BIG), 1.5) },
    overcast: { ink: up(overcast, 1.5) },
    'few-day-wet': few(false, -4),
    'few-night-wet': few(true, -4),
    'cloudy-wet': { ink: up(cloud(BIG), -3) },
    'overcast-wet': { ink: up(overcast, -3) },
    thunder: { sun: BOLT, ink: up(overcast, -3) },
    snow: {
      ink: up(overcast, -3) + flake(11, 26.5) + flake(16.5, 29) + flake(22, 26.5)
    },
    fog: {
      ink: [
        [7, 25, 11],
        [5, 27, 15.5],
        [7, 25, 20],
        [10, 22, 24.5]
      ]
        .map(([a, b, y]) => `<line class="y-ink" x1="${a}" y1="${y}" x2="${b}" y2="${y}"/>`)
        .join('')
    }
  };
}

const SKIES = skies();

const DROPS: Record<string, string> = {
  'drops-maybe': drop(16, 23.6, 1, true),
  'drops-1': drop(16, 23.4, 1),
  'drops-2': drop(12.5, 23.4, 1) + drop(19.5, 23.4, 1),
  'drops-3': drop(10, 23.8, 0.85) + drop(16, 23.8, 0.85) + drop(22, 23.8, 0.85)
};

// Interface icons on a 16 x 16 grid, in the text colour around them.
const ICONS: Record<string, string> = {
  info: '<circle class="i" cx="8" cy="8" r="6.5"/><path class="i" d="M8 7.2v4.3M8 4.6v.4"/>',
  warn: '<path class="i" d="M8 1.5 15 14H1z"/><path class="i" d="M8 6v3.6M8 11.4v.4"/>',
  bad: '<circle class="i" cx="8" cy="8" r="6.5"/><path class="i" d="M5.5 5.5l5 5M10.5 5.5l-5 5"/>',
  ok: '<path class="i" d="M3 8.5l3 3L13 4.5"/>',
  off: '<path class="i" d="M1.5 6a9.5 9.5 0 0 1 13 0M3.8 8.6a6 6 0 0 1 8.4 0M6.2 11.1a2.6 2.6 0 0 1 3.6 0M2 2l12 12"/>',
  play: '<path class="i-dot" d="M4 2.5v11l9-5.5z"/>',
  pause: '<path class="i-dot" d="M4 2.5h3v11H4zM9 2.5h3v11H9z"/>'
};

export const SYMBOL_IDS = [...Object.keys(SKIES), ...Object.keys(DROPS)];
export const ICON_IDS = Object.keys(ICONS);

const symbol = (id: string, body: string) =>
  `<symbol id="${id}" viewBox="0 0 32 32">${body}</symbol>`;

export function sprite(): string {
  const layered = Object.entries(SKIES).flatMap(([id, { sun: s, ink }]) => {
    if (Boolean(s) !== sunLayer(id) || Boolean(ink) !== inkLayer(id))
      throw new Error(`${id}: its layers do not match layers.ts`);
    const parts = [
      ...(s ? [symbol(`${id}-sun`, s)] : []),
      ...(ink ? [symbol(`${id}-ink`, ink)] : [])
    ];
    const both = [s ? `<use href="#${id}-sun"/>` : '', ink ? `<use href="#${id}-ink"/>` : ''];
    return [...parts, symbol(id, both.join(''))];
  });
  const drops = Object.entries(DROPS).map(([id, body]) => symbol(id, body));
  const icons = Object.entries(ICONS).map(
    ([id, body]) => `<symbol id="i-${id}" viewBox="0 0 16 16">${body}</symbol>`
  );
  return `<svg xmlns="http://www.w3.org/2000/svg">${[...layered, ...drops, ...icons].join('')}</svg>`;
}

// The tab icon: the few-day symbol on its own.
export const favicon = () => {
  const { sun: s, ink } = SKIES['few-day'] ?? {};
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><style>${FAVICON_STYLE}</style>${s ?? ''}${ink ?? ''}</svg>
`;
};
