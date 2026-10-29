// The hours ahead as the hero tells them: one sentence on rain over the next
// 12 hours and six cells two hours apart. Rain at a step counts the hour that
// ends there, so a cell or a sentence names the hour the rain starts.
import { t } from '#lib/copy/t.ts';
import { nextHour } from '#lib/chart/h48.ts';
import { models } from '#lib/format.ts';
import { pick, type Sky } from '#lib/symbols/pick.ts';
import { dayName, hm, HOUR_MS, isNight, ymd } from '#lib/time.ts';
import type { ForecastFile } from '#lib/data/decode.ts';

type Hourly = ForecastFile['hourly'];
const AHEAD_H = 12;
const STEP_H = 2;

// Most models from half of them up; any single model is still named, since the
// sentence for none says that none of them gives rain.
export function verdict(hourly: Hourly, now: number): string {
  const times = hourly.time.map(Date.parse);
  let most = -1;
  let some = -1;
  let counted = 0;
  times.forEach((time, i) => {
    if (time < now - HOUR_MS || time > now + AHEAD_H * HOUR_MS) return;
    const n = hourly.rain.n_models[i] ?? 0;
    const m = hourly.rain.m_models[i] ?? 0;
    counted = Math.max(counted, m);
    if (most < 0 && m && n / m >= 0.5) most = i;
    if (some < 0 && n > 0) some = i;
  });
  const when = (i: number) => {
    const start = (times[i] ?? now) - HOUR_MS;
    if (start <= now)
      return t('h48.summary_by', { ora: hm((Math.floor(now / HOUR_MS) + 1) * HOUR_MS) });
    if (ymd(start) === ymd(now)) return t('h48.summary_from', { ora: hm(start) });
    return t('h48.summary_from_day', { giorno: dayName(start, now), ora: hm(start) });
  };
  const at = (i: number) => models(hourly.rain.n_models[i] ?? 0, hourly.rain.m_models[i] ?? 0);
  if (most >= 0) return t('verdict.rain_most', { quando: when(most), modelli: at(most) });
  if (some >= 0) return t('verdict.rain_some', { quando: when(some), modelli: at(some) });
  return t('verdict.rain_none', { m: counted });
}

export type Cell = {
  time: number;
  temp: number | null;
  sky: Sky;
  rainy: number;
  counted: number;
};

// Six cells from the next full hour, each with the sky and the most models
// giving rain over the two hours that follow it, as the chart's symbols do.
export function strip(hourly: Hourly, now: number, lat: number, lon: number): Cell[] {
  const times = hourly.time.map(Date.parse);
  const first = nextHour(times, now);
  const cells: Cell[] = [];
  for (let k = 0; k < AHEAD_H / STEP_H; k++) {
    const i = first + k * STEP_H;
    const block = [i + 1, i + 2].filter((j) => j < times.length);
    if (i >= times.length || block.length < STEP_H) break;
    const clouds = block.map((j) => hourly.cloud_pct.mean[j]).filter((v) => v != null);
    const cloud = clouds.length ? clouds.reduce((a, b) => a + b, 0) / clouds.length : null;
    let rainy = 0;
    let counted = hourly.rain.m_models[block[0]!] ?? 0;
    let wettest = 0;
    for (const j of block) {
      const n = hourly.rain.n_models[j] ?? 0;
      const m = hourly.rain.m_models[j] ?? 0;
      if (m && n / m > rainy / (counted || 1)) [rainy, counted] = [n, m];
      wettest = Math.max(wettest, hourly.precipitation_mm.mean[j] ?? 0);
    }
    const mid = times[i]! + HOUR_MS;
    cells.push({
      time: times[i]!,
      temp: hourly.temperature_c.mean[i] ?? null,
      sky: pick(cloud, rainy, counted || 1, wettest, isNight(mid, lat, lon), false),
      rainy,
      counted
    });
  }
  return cells;
}
