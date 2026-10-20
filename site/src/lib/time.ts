// Every time the site handles is UTC milliseconds; Europe/Rome appears only
// here, where a time becomes text.
import { t } from '#lib/copy/t.ts';

const ZONE = 'Europe/Rome';
const rome = (options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat('it-IT', { timeZone: ZONE, ...options });

const HM = rome({ hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const HOUR = rome({ hour: '2-digit', hourCycle: 'h23' });
const WEEKDAY_SHORT = rome({ weekday: 'short' });
const WEEKDAY_LONG = rome({ weekday: 'long' });
const DAY = rome({ day: 'numeric' });
const DAY_MONTH = rome({ day: 'numeric', month: 'short' });
// en-CA writes the date as 2026-10-25, which compares and sorts as text.
const YMD = new Intl.DateTimeFormat('en-CA', {
  timeZone: ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit'
});

export const MINUTE = 60_000;
export const HOUR_MS = 3_600_000;
const DAY_MS = 86_400_000;

export const hm = (ms: number) => HM.format(ms);
export const hour = (ms: number) => HOUR.format(ms);
export const ymd = (ms: number) => YMD.format(ms);
export const weekdayShort = (ms: number) => WEEKDAY_SHORT.format(ms).replace('.', '');
export const weekdayLong = (ms: number) => WEEKDAY_LONG.format(ms);
export const dayNumber = (ms: number) => DAY.format(ms);
export const dayMonth = (ms: number) => DAY_MONTH.format(ms);

// A local date of the contract, such as "2026-10-26". Noon UTC falls on the
// same date in Rome all year, so the formatters above read it back unchanged.
export const localDate = (day: string) => Date.parse(`${day}T12:00:00Z`);

export function ago(ms: number, now: number): string {
  const minutes = Math.max(0, Math.floor((now - ms) / MINUTE));
  if (minutes < 1) return t('time.just_now');
  if (minutes < 60) return t('time.min_ago', { n: minutes });
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours >= 3) return t('time.hours_ago', { n: hours });
  if (hours === 1 && rest === 0) return t('time.hour_ago');
  return t('time.hm_ago', { h: hours, m: rest });
}

// "oggi", "domani", "ieri" or the weekday, for sentences such as "domani dalle 17:00".
export function dayName(ms: number, now: number): string {
  const day = ymd(ms);
  if (day === ymd(now)) return t('d10.today').toLowerCase();
  if (day === ymd(now + DAY_MS)) return t('d10.tomorrow').toLowerCase();
  if (day === ymd(now - DAY_MS)) return t('time.yesterday');
  return weekdayLong(ms);
}

// On the night summer time ends the hour from 02:00 to 03:00 comes twice. Of
// two hourly steps with the same local hour, the first is still summer time.
export function repeatedHour(times: number[], i: number): 'summer' | 'winter' | null {
  const at = times[i];
  if (at === undefined) return null;
  const next = times[i + 1];
  const previous = times[i - 1];
  if (next !== undefined && hour(next) === hour(at)) return 'summer';
  if (previous !== undefined && hour(previous) === hour(at)) return 'winter';
  return null;
}

export function dstLabel(times: number[], i: number): string | null {
  const which = repeatedHour(times, i);
  if (which === 'summer') return t('h48.cell_dst_before');
  if (which === 'winter') return t('h48.cell_dst');
  return null;
}

// The sun's elevation in degrees, good to a fraction of a degree (the NOAA
// approximation the design uses for night shading and the moon symbol).
export function sunElevation(ms: number, lat: number, lon: number): number {
  const rad = Math.PI / 180;
  const d = ms / DAY_MS - 10957.5;
  const g = (357.529 + 0.98560028 * d) * rad;
  const q = 280.459 + 0.98564736 * d;
  const ecliptic = (q + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * rad;
  const tilt = (23.439 - 0.00000036 * d) * rad;
  const ascension = Math.atan2(Math.cos(tilt) * Math.sin(ecliptic), Math.cos(ecliptic));
  const declination = Math.asin(Math.sin(tilt) * Math.sin(ecliptic));
  const sidereal = (18.697374558 + 24.06570982441908 * d) % 24;
  const angle = (sidereal * 15 + lon) * rad - ascension;
  const phi = lat * rad;
  const sine =
    Math.sin(phi) * Math.sin(declination) + Math.cos(phi) * Math.cos(declination) * Math.cos(angle);
  return Math.asin(sine) / rad;
}

// Below -0.833 degrees the sun's upper edge is under the horizon.
export const isNight = (ms: number, lat: number, lon: number) =>
  sunElevation(ms, lat, lon) < -0.833;
