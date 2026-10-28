// The weather symbols and interface icons, drawn on a 32 x 32 grid for this
// site, written at build time into one sprite that each town page carries in its
// own HTML. app.css colours the classes with the page's tokens: WebKit and
// Firefox do not pass the tokens into a sprite read from a file by <use>.

// The favicon is drawn by the browser outside the page, so it has its own
// colours, the light theme's.
const FAVICON_STYLE = `
.s-sun{fill:#e9a10b}
.s-ray{stroke:#e9a10b;stroke-width:2;stroke-linecap:round}
.s-cloud{fill:#e9ecf0}
.s-edge{fill:#7f8996}`;

const n = (x: number) => Number(x.toFixed(2));

function sun(cx: number, cy: number, r: number, ray: number): string {
  let s = `<circle class="s-sun" cx="${cx}" cy="${cy}" r="${r}"/>`;
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    const [c, si] = [Math.cos(a), Math.sin(a)];
    s += `<line class="s-ray" x1="${n(cx + c * (r + 2))}" y1="${n(cy + si * (r + 2))}" x2="${n(cx + c * (r + 2 + ray))}" y2="${n(cy + si * (r + 2 + ray))}"/>`;
  }
  return s;
}

const moon = (cx: number, cy: number, r: number) =>
  `<path class="s-moon" d="M${n(cx + r * 0.35)} ${cy - r} A${r} ${r} 0 1 0 ${cx + r} ${n(cy + r * 0.45)} A${n(r * 0.8)} ${n(r * 0.8)} 0 0 1 ${n(cx + r * 0.35)} ${cy - r} Z"/>`;

type Cloud = { circles: [number, number, number][]; box: [number, number, number, number] };

// A cloud is circles and a box; its outline is the same shapes, drawn larger behind.
function shapes(c: Cloud, grow: number): string {
  const circles = c.circles.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${n(r + grow)}"/>`);
  const [x, y, w, h] = c.box;
  return `${circles.join('')}<rect x="${n(x - grow)}" y="${n(y - grow)}" width="${n(w + 2 * grow)}" height="${n(h + 2 * grow)}" rx="${grow}"/>`;
}
const cloud = (c: Cloud, fill: string) =>
  `<g class="s-edge">${shapes(c, 1.3)}</g><g class="${fill}">${shapes(c, 0)}</g>`;

const BIG: Cloud = {
  circles: [
    [10.5, 19, 5.5],
    [17, 14.5, 7.5],
    [23.5, 19, 5.5]
  ],
  box: [10.5, 17, 13, 7.5]
};
const SMALL: Cloud = {
  circles: [
    [15.5, 23, 4.2],
    [21, 19.5, 5.8],
    [26.2, 23.2, 4]
  ],
  box: [15.5, 21, 10.7, 6.2]
};
const BACK: Cloud = {
  circles: [
    [14, 12.5, 5],
    [20, 9.5, 6],
    [25.5, 13, 4.2]
  ],
  box: [14, 11, 11.5, 6.2]
};

function drop(x: number, y: number, s: number, hollow = false): string {
  const d = `M${x} ${y} C${x} ${y} ${n(x - 2.3 * s)} ${n(y + 3 * s)} ${n(x - 2.3 * s)} ${n(y + 4.2 * s)} A${n(2.3 * s)} ${n(2.3 * s)} 0 0 0 ${n(x + 2.3 * s)} ${n(y + 4.2 * s)} C${n(x + 2.3 * s)} ${n(y + 3 * s)} ${x} ${y} ${x} ${y} Z`;
  return `<path class="${hollow ? 's-rain-line' : 's-rain'}" d="${d}"/>`;
}

const up = (inner: string, dy: number) => `<g transform="translate(0 ${dy})">${inner}</g>`;
const few = (night: boolean) =>
  (night ? moon(11, 11, 7) : sun(11.5, 11.5, 4.6, 2.4)) + cloud(SMALL, 's-cloud');
const overcast = () => cloud(BACK, 's-cloud-back') + up(cloud(BIG, 's-cloud'), 1.5);

// A base is the sky without rain; its -wet form sits higher to leave room for drops.
const SYMBOLS: Record<string, string> = {
  'clear-day': sun(16, 16, 6, 3),
  'clear-night': moon(15, 16, 9),
  'few-day': few(false),
  'few-night': few(true),
  cloudy: cloud(BIG, 's-cloud'),
  overcast: overcast(),
  'few-day-wet': up(few(false), -4),
  'few-night-wet': up(few(true), -4),
  'cloudy-wet': up(cloud(BIG, 's-cloud'), -3.5),
  'overcast-wet': up(overcast(), -4),
  'drops-maybe': drop(16, 24.6, 1, true),
  'drops-1': drop(16, 24.4, 1),
  'drops-2': drop(12.5, 24.4, 1) + drop(19.5, 24.4, 1),
  'drops-3': drop(10, 24.8, 0.85) + drop(16, 24.8, 0.85) + drop(22, 24.8, 0.85),
  thunder:
    up(overcast(), -4) +
    '<path class="s-sun" d="M17.6 21.5 L13.2 27.6 H16.3 L14.6 31.6 L19.8 25.2 H16.8 L18.8 21.5 Z"/>',
  snow:
    up(overcast(), -4) +
    [11.5, 16.5, 21.5]
      .map((x, i) => `<circle class="s-snow" cx="${x}" cy="${i === 1 ? 29.5 : 26.5}" r="1.6"/>`)
      .join(''),
  fog: [
    [7, 25, 11],
    [4, 28, 16],
    [7, 25, 21],
    [10, 22, 26]
  ]
    .map(([a, b, y]) => `<line class="s-fog" x1="${a}" y1="${y}" x2="${b}" y2="${y}"/>`)
    .join('')
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

export const SYMBOL_IDS = Object.keys(SYMBOLS);
export const ICON_IDS = Object.keys(ICONS);

export function sprite(): string {
  const symbols = Object.entries(SYMBOLS).map(
    ([id, body]) => `<symbol id="${id}" viewBox="0 0 32 32">${body}</symbol>`
  );
  const icons = Object.entries(ICONS).map(
    ([id, body]) => `<symbol id="i-${id}" viewBox="0 0 16 16">${body}</symbol>`
  );
  return `<svg xmlns="http://www.w3.org/2000/svg">${[...symbols, ...icons].join('')}</svg>`;
}

// The tab icon: the few_day symbol on its own.
export const favicon = () =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><style>${FAVICON_STYLE}</style>${SYMBOLS['few-day']}</svg>
`;
