// Where the public files are and when each should change.
import {
  decodeForecast,
  decodeNow,
  decodeRadar,
  decodeStatus,
  type ForecastFile,
  type NowFile,
  type RadarFile
} from './decode.ts';
import type { Status } from '#gen/status.ts';
import type { Env, Source } from './refresh.ts';

export const PUBLIC = 'https://stkaystackmeteopubprod.blob.core.windows.net/public';
// In development the dev server answers /data from the fixtures or the account.
export const DATA = import.meta.env.DEV ? '/data' : PUBLIC;

const MIN = 60_000;
const at = (stamp: string) => Date.parse(stamp);

// A radar frame reaches the account about two minutes after its 5-minute slot,
// a METAR about seven after its half hour, and the forecast is issued hourly.
const NEXT_FRAME = 7 * MIN;
const NEXT_METAR = 37 * MIN;
const NEXT_ISSUE = 63 * MIN;

export function nowFile(slug: string): Source<NowFile> {
  return {
    url: `${DATA}/v1/${slug}/now.json`,
    decode: decodeNow,
    due: (now) => {
      const times = [
        now.radar ? at(now.radar.frame_time) + NEXT_FRAME : Infinity,
        now.metar ? at(now.metar.observed_at) + NEXT_METAR : Infinity
      ];
      const first = Math.min(...times);
      return Number.isFinite(first) ? first : at(now.generated_at) + 10 * MIN;
    }
  };
}

export function forecastFile(slug: string): Source<ForecastFile> {
  return {
    url: `${DATA}/v1/${slug}/forecast.json`,
    decode: decodeForecast,
    due: (forecast) => at(forecast.generated_at) + NEXT_ISSUE
  };
}

export function radarFile(slug: string): Source<RadarFile> {
  return {
    url: `${DATA}/v1/${slug}/radar.json`,
    decode: decodeRadar,
    due: (radar) => {
      const last = radar.frames.at(-1);
      return (last ? at(last.time) : at(radar.generated_at)) + NEXT_FRAME;
    }
  };
}

// The sprite named by radar.json, next to it. Each update has a new name, so it
// is read once, not followed.
export const spriteUrl = (slug: string, name: string) => `${DATA}/v1/${slug}/${name}`;

export function statusFile(): Source<Status> {
  return { url: `${DATA}/status.json`, decode: decodeStatus, due: () => Infinity, lazy: true };
}

// In development `?now=2026-10-24T13:10:00Z` sets the page's clock, so the
// fixtures, written for that Saturday, read as fresh. Builds leave it out.
function clockShift(): number {
  if (!import.meta.env.DEV) return 0;
  const now = Date.parse(new URLSearchParams(location.search).get('now') ?? '');
  return Number.isNaN(now) ? 0 : now - Date.now();
}

export function browserEnv(): Env {
  const shift = clockShift();
  return {
    now: () => Date.now() + shift,
    hidden: () => document.visibilityState === 'hidden',
    online: () => navigator.onLine,
    wait: (ms, then) => {
      const id = setTimeout(then, ms);
      return () => clearTimeout(id);
    },
    onShow: (then) => {
      const visible = () => document.visibilityState === 'visible' && then();
      document.addEventListener('visibilitychange', visible);
      window.addEventListener('online', then);
      return () => {
        document.removeEventListener('visibilitychange', visible);
        window.removeEventListener('online', then);
      };
    },
    // The browser cache answers within the files' max-age and revalidates
    // with their ETag after it, without a preflight.
    get: async (url, kind) => {
      const response = await fetch(url, { signal: AbortSignal.timeout(15_000) });
      return {
        status: response.status,
        etag: response.headers.get('ETag'),
        body: () => (kind === 'blob' ? response.blob() : response.json())
      };
    }
  };
}
