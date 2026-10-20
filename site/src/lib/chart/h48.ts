// The parts of the 48-hour view that are rules rather than drawing: which hours
// are shown, the summary sentence, and the steps of the axes.
import { t } from '#lib/copy/t.ts';
import { temp } from '#lib/format.ts';
import { dayName, hm, HOUR_MS, ymd } from '#lib/time.ts';
import type { ForecastFile } from '#lib/data/decode.ts';

type Hourly = ForecastFile['hourly'];

// The first hour shown is the last one already started: past hours are trimmed.
export function firstShown(times: number[], now: number): number {
  let first = 0;
  times.forEach((time, i) => {
    if (time <= now) first = i;
  });
  return first;
}

// The hour picked when the page opens: the next full hour.
export function nextHour(times: number[], now: number): number {
  const i = times.findIndex((time) => time >= now);
  return i === -1 ? times.length - 1 : i;
}

// A round step that gives about `target` ticks over `range`.
export function niceStep(range: number, target: number): number {
  const raw = range / target;
  const power = 10 ** Math.floor(Math.log10(raw));
  const m = raw / power;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * power;
}

// Fixed rules over the next 12 hours: when most models give rain, else when a
// fifth do, then the temperature range of the 48 hours. Rain counts the hour
// ending at a step, so the sentence names the hour it starts.
export function summary(hourly: Hourly, now: number): { rain: string; temp: string } {
  const times = hourly.time.map(Date.parse);
  let most = -1;
  let some = -1;
  times.forEach((time, i) => {
    if (time < now - HOUR_MS || time > now + 12 * HOUR_MS) return;
    const m = hourly.rain.m_models[i] ?? 0;
    const share = m ? (hourly.rain.n_models[i] ?? 0) / m : 0;
    if (most < 0 && share >= 0.5) most = i;
    if (some < 0 && share >= 0.2) some = i;
  });
  const when = (i: number) => {
    const start = (times[i] ?? now) - HOUR_MS;
    if (start <= now) return t('h48.summary_now');
    if (ymd(start) === ymd(now)) return t('h48.summary_from', { ora: hm(start) });
    return t('h48.summary_from_day', { giorno: dayName(start, now), ora: hm(start) });
  };
  const rain =
    most >= 0
      ? t('h48.summary_rain_most', { quando: when(most) })
      : some >= 0
        ? t('h48.summary_rain_some', { quando: when(some) })
        : t('h48.summary_rain_none');
  const values = hourly.temperature_c.mean.filter(
    (v, i): v is number => v !== null && (times[i] ?? 0) >= now - HOUR_MS
  );
  const range = values.length
    ? t('h48.summary_temp', { min: temp(Math.min(...values)), max: temp(Math.max(...values)) })
    : '';
  return { rain, temp: range };
}

// The last hour that still has every model of the first one, for the footnote.
export function lastFullHour(hourly: Hourly): number {
  const first = hourly.temperature_c.m_models[0] ?? 0;
  let last = 0;
  hourly.temperature_c.m_models.forEach((m, i) => {
    if (m === first) last = i;
  });
  return last;
}
