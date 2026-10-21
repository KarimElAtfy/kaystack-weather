// Numbers as the site prints them: Italian decimals, whole degrees and km/h,
// and the units from the copy file.
import { has, t, type Key } from '#lib/copy/t.ts';

type Value = number | null | undefined;

const WHOLE = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 0 });
const ONE = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const missing = (x: Value): x is null | undefined => x === null || x === undefined;
const trim = (text: string) => text.replace(/,0$/, '');

// + 0 turns the -0 that Math.round gives for -0.4 into 0, which would
// otherwise print as "-0".
export const int = (x: Value) => (missing(x) ? t('state.nodata') : WHOLE.format(Math.round(x) + 0));
export const dec = (x: Value) => (missing(x) ? t('state.nodata') : ONE.format(x));

export const temp = (x: Value) => (missing(x) ? t('state.nodata') : `${int(x)} ${t('unit.c')}`);
export const deg = (x: Value) => (missing(x) ? t('state.nodata') : `${int(x)}°`);
export const kmh = (x: Value) => (missing(x) ? t('state.nodata') : `${int(x)} ${t('unit.kmh')}`);
export const mmh = (x: Value) => (missing(x) ? t('state.nodata') : `${dec(x)} ${t('unit.mmh')}`);
export const km = (x: number) => `${trim(dec(x))} ${t('unit.km')}`;
export const pct = (x: Value) => (missing(x) ? t('state.nodata') : `${int(x)}${t('unit.pct')}`);

export function mm(x: Value): string {
  if (missing(x)) return t('state.nodata');
  return `${x > 0 && x < 0.1 ? '<0,1' : dec(x)} ${t('unit.mm')}`;
}

// METAR visibility: 9999 means 10 km or more.
export function visibility(metres: Value): string {
  if (missing(metres)) return t('state.nodata');
  if (metres >= 9999) return t('vis.max');
  if (metres >= 5000) return `${int(metres / 1000)} ${t('unit.km')}`;
  if (metres >= 1000) return `${trim(dec(metres / 1000))} ${t('unit.km')}`;
  return `${int(metres)} ${t('unit.m')}`;
}

const POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'] as const;
export type Point = (typeof POINTS)[number];

export function point(degrees: Value): Point | null {
  if (missing(degrees)) return null;
  return POINTS[Math.round((((degrees % 360) + 360) % 360) / 45) % 8] ?? null;
}

export const directionLong = (p: Point) => t(`dirlong.${p}`);
export const directionShort = (p: Point) => t(`dir.${p}`);

// Under 2 km/h a mean wind has no useful direction.
export function wind(speed: Value, degrees: Value): string {
  if (missing(speed)) return t('state.nodata');
  if (speed < 2) return t('wind.calm');
  const p = point(degrees);
  const from = p ? t('wind.from', { dir: directionLong(p) }) : t('wind.variable');
  return `${kmh(speed)} ${from}`;
}

export function models(n: number, m: number): string {
  if (n === 0) return t('models.none', { m });
  if (n === 1) return t('models.one', { m });
  return t('models.many', { n, m });
}

// Relative humidity from temperature and dew point (Magnus formula).
export function humidity(temperature: Value, dewPoint: Value): number | null {
  if (missing(temperature) || missing(dewPoint)) return null;
  const e = (x: number) => Math.exp((17.625 * x) / (243.04 + x));
  return Math.round((100 * e(dewPoint)) / e(temperature));
}

const DESCRIPTORS = ['MI', 'BC', 'PR', 'DR', 'BL', 'SH', 'TS', 'FZ'];
const AFTER = ['MI', 'BC', 'PR', 'BL', 'DR', 'FZ'];

// One METAR weather group, such as -SHRA, into Italian: intensity, kind,
// phenomenon, in the order the copy file describes.
function group(code: string): string {
  let rest = code;
  const sign = rest.startsWith('-') || rest.startsWith('+') ? rest.charAt(0) : '';
  rest = rest.slice(sign.length);
  const vicinity = rest.startsWith('VC');
  if (vicinity) rest = rest.slice(2);
  const descriptors = DESCRIPTORS.filter((d) => {
    if (!rest.startsWith(d)) return false;
    rest = rest.slice(2);
    return true;
  });
  const keys: Key[] = [];
  while (rest.length >= 2) {
    const key = `wx.${rest.slice(0, 2)}`;
    if (!has(key)) return t('wx.unknown', { codice: code });
    keys.push(key);
    rest = rest.slice(2);
  }
  if (rest.length) return t('wx.unknown', { codice: code });
  const words = keys.map((key) => t(key)).join(' e ');
  const showers = descriptors.includes('SH');
  let text: string;
  if (descriptors.includes('TS')) text = keys.length ? `${t('wx.TS_with')} ${words}` : t('wx.TS');
  // The copy has no word yet for showers of nothing named, as in VCSH.
  else if (showers && !keys.length) return t('wx.unknown', { codice: code });
  else if (showers) text = `${t('wx.SH')} ${words}`;
  else {
    text = words;
    for (const d of AFTER) {
      const key = `wx.${d}`;
      if (descriptors.includes(d) && has(key)) text += ` ${t(key)}`;
    }
  }
  if (sign === '-') text += ` ${t(showers ? 'wx.light_pl' : 'wx.light')}`;
  if (sign === '+') text += ` ${t(showers ? 'wx.heavy_pl' : 'wx.heavy')}`;
  if (vicinity) text += ` ${t('wx.vicinity')}`;
  return text;
}

export function weather(groups: string | null | undefined): string | null {
  const trimmed = groups?.trim();
  if (!trimmed) return null;
  const text = trimmed.split(/\s+/).map(group).join(', ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}
