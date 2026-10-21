// How fresh each block is, with the thresholds of SITE-SPEC section 2. A stale
// value is shown muted with its time; an expired one is not shown at all.
import type { Source as StatusSource } from '#gen/status.ts';
import type { ForecastFile, NowFile } from './decode.ts';
import type { Reading } from './refresh.ts';

export type Freshness = 'fresh' | 'stale' | 'expired';

const MIN = 60_000;
const age = (stamp: string, now: number) => (now - Date.parse(stamp)) / MIN;

function judge(minutes: number, stale: number, expired: number): Freshness {
  if (minutes <= stale) return 'fresh';
  if (minutes <= expired) return 'stale';
  return 'expired';
}

export const metarFreshness = (metar: NonNullable<NowFile['metar']>, now: number) =>
  judge(age(metar.observed_at, now), metar.stale_after_min, 180);

export const radarAtTownFreshness = (radar: NonNullable<NowFile['radar']>, now: number) =>
  judge(age(radar.frame_time, now), radar.stale_after_min, 60);

// The hour of frames stays worth showing for a while after it stops updating.
export const radarMapFreshness = (lastFrame: string, staleAfterMin: number, now: number) =>
  judge(age(lastFrame, now), staleAfterMin, 180);

export const forecastFreshness = (forecast: ForecastFile, now: number) =>
  judge(age(forecast.issued_at, now), forecast.stale_after_min, forecast.expired_after_min);

// The one state of the whole page that the status line shows, in the
// designer's order: offline, unreachable, missing, old, stale, normal. The
// forecast is judged at its last read, so the state changes with the data,
// never with the clock alone.
export type PageState = 'loading' | 'offline' | 'failed' | 'missing' | 'old' | 'stale' | 'ok';

export function pageState(
  reads: Reading<unknown>[],
  forecast: Reading<ForecastFile>,
  now: number
): PageState {
  if (reads.some((read) => read.problem === 'offline')) return 'offline';
  if (reads.some((read) => read.problem === 'unavailable' || read.problem === 'invalid')) {
    return 'failed';
  }
  if (!forecast.value) return forecast.problem ? 'missing' : 'loading';
  const freshness = forecastFreshness(forecast.value, forecast.at ?? now);
  return freshness === 'expired' ? 'old' : freshness === 'stale' ? 'stale' : 'ok';
}

export type SourceState = 'ok' | 'late' | 'down';

// Minutes. "down": the pipeline has not reached the source for this long;
// "late": its newest data is this old (the plan's freshness limits).
const LIMITS: Record<string, { late: number; down: number }> = {
  metar: { late: 90, down: 90 },
  radar: { late: 30, down: 20 },
  'open-meteo': { late: 360, down: 180 },
  arpa: { late: 1080, down: 360 }
};

export const SOURCES = Object.keys(LIMITS);

export function sourceState(name: string, source: StatusSource, now: number): SourceState {
  const limit = LIMITS[name];
  if (!limit || source.checked_at === null || source.data_time === null) return 'down';
  if (age(source.checked_at, now) > limit.down) return 'down';
  if (age(source.data_time, now) > limit.late) return 'late';
  return 'ok';
}
