// Oggi, Stanotte and the labels on the 48-hour line, all read from the
// corrected hourly mean, so the pair under the verdict and the chart show the
// same number. Domani and the ten days use the daily file instead: the mean of
// each model's maximum runs higher than the peak of the mean curve, because the
// models peak at different hours.
import { firstShown } from '#lib/chart/h48.ts';
import { hour, localDate, ymd } from '#lib/time.ts';
import type { ForecastFile } from '#lib/data/decode.ts';

type Hourly = ForecastFile['hourly'];
const DAY_MS = 86_400_000;

// A value read on the line: the index of its hour in the file, and the value.
export type Reading = { i: number; value: number };
export type Label = Reading & { kind: 'high' | 'low' };

// Nights run from 18:00 to 09:00, named after the evening they start on.
const EVENING = 18;
const MORNING = 9;
// Before 06:00 "stanotte" still means the night under way.
const DAWN = 6;
// From 15:00 the pair under the verdict reads Stanotte and Domani, not Oggi.
const AFTERNOON = 15;
const HALF_DAY_MS = 43_200_000;

const local = (ms: number) => Number(hour(ms));
const night = (ms: number) => {
  const h = local(ms);
  if (h >= EVENING) return ymd(ms);
  // Twelve hours back lands on the evening before, on either side of a clock change.
  if (h < MORNING) return ymd(ms - HALF_DAY_MS);
  return null;
};

// The hours of one window, from `from` on. A window cut by the end of the file
// is not one: its lowest hour would only be the last hour there is.
function window(times: number[], from: number, key: (ms: number) => string | null, name: string) {
  const hours: number[] = [];
  for (let i = from; i < times.length; i++) {
    if (key(times[i]!) === name) hours.push(i);
    else if (hours.length) return hours;
  }
  return null;
}

// A window with an hour the correction did not reach shows no figure at all.
function pick(hourly: Hourly, hours: number[] | null, kind: Label['kind']): Reading | null {
  if (!hours?.length) return null;
  const mean = hourly.temperature_c.mean;
  if (hours.some((i) => mean[i] == null)) return null;
  const better =
    kind === 'high' ? (a: number, b: number) => b > a : (a: number, b: number) => b < a;
  const i = hours.reduce((found, i) => (better(mean[found]!, mean[i]!) ? i : found));
  return { i, value: mean[i]! };
}

// The highest hour still to come today. Null once today is over in the file,
// or when the file holds no hour of today.
export function today(hourly: Hourly, now: number): Reading | null {
  const times = hourly.time.map(Date.parse);
  const from = firstShown(times, now);
  return pick(hourly, window(times, from, ymd, ymd(now)), 'high');
}

// The lowest hour of the night under way before 06:00, of the coming night from
// 06:00, counting only the hours from now on.
const nightName = (now: number) => (local(now) < DAWN ? ymd(now - HALF_DAY_MS) : ymd(now));

export function tonight(hourly: Hourly, now: number): Reading | null {
  const times = hourly.time.map(Date.parse);
  return pick(hourly, window(times, firstShown(times, now), night, nightName(now)), 'low');
}

// One high per day and one low per night along the 48 hours. Today and the
// night under way take the readings of the pair, today only while the pair
// shows it; any other window counts only when the file holds all of it.
export function labels(hourly: Hourly, now: number): Label[] {
  const times = hourly.time.map(Date.parse);
  const from = firstShown(times, now);
  const out: Label[] = [];
  const high = local(now) < AFTERNOON ? today(hourly, now) : null;
  const low = tonight(hourly, now);
  if (high) out.push({ ...high, kind: 'high' });
  if (low) out.push({ ...low, kind: 'low' });
  const seen = new Set([`high ${ymd(now)}`, `low ${nightName(now)}`]);
  for (let i = from; i < times.length; i++) {
    for (const [kind, key] of [
      ['high', ymd],
      ['low', night]
    ] as const) {
      const name = key(times[i]!);
      if (name === null || seen.has(`${kind} ${name}`)) continue;
      seen.add(`${kind} ${name}`);
      // A window already open when the line starts is not whole.
      if (i > 0 && key(times[i - 1]!) === name) continue;
      const reading = pick(hourly, window(times, i, key, name), kind);
      if (reading) out.push({ ...reading, kind });
    }
  }
  return out.sort((a, b) => a.i - b.i);
}

export type Figure = { word: 'today' | 'tonight' | 'tomorrow'; value: number | null };

// The two figures under the verdict. A null value is a figure not to show.
export function pair(forecast: ForecastFile, now: number): [Figure, Figure] {
  const low: Figure = { word: 'tonight', value: tonight(forecast.hourly, now)?.value ?? null };
  if (local(now) < AFTERNOON)
    return [{ word: 'today', value: today(forecast.hourly, now)?.value ?? null }, low];
  const k = forecast.daily.day.indexOf(ymd(localDate(ymd(now)) + DAY_MS));
  return [low, { word: 'tomorrow', value: k < 0 ? null : (forecast.daily.tmax_c.mean[k] ?? null) }];
}
