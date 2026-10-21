// Checks a public file before the page uses it. It looks only at what the site
// reads, ignores fields it does not know, and treats as optional the fields
// added to v1 after the first files were written. Anything else that is off
// throws, and the page shows that one block as unavailable.
import type { Consensus, Forecast } from '#gen/forecast.ts';
import type { Metar, Now } from '#gen/now.ts';
import type { Frame, Radar } from '#gen/radar.ts';
import type { Status } from '#gen/status.ts';

export class DecodeError extends Error {}

// Requested additions to v1 (SITE-SPEC B1 to B3).
export type MetarExtra = Metar & { raw?: string | null; cloud_cover?: string | null };
export type FrameExtra = Frame & { town_mm_h?: number | null; max_10km_mm_h?: number | null };
export type DailyExtra = {
  cloud_pct?: Consensus;
  precipitation_mm?: Consensus;
  wind_max_kmh?: Consensus;
  gust_max_kmh?: Consensus;
};
export type NowFile = Now & { metar: MetarExtra | null };
export type ForecastFile = Forecast & { daily: Forecast['daily'] & DailyExtra };
export type RadarFile = Radar & { frames: FrameExtra[] };

type Obj = Record<string, unknown>;

const fail = (path: string, problem: string): never => {
  throw new DecodeError(`${path}: ${problem}`);
};

function object(value: unknown, path: string): Obj {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    fail(path, 'not an object');
  return value as Obj;
}

function number(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) fail(path, 'not a number');
  return value as number;
}

function maybeNumber(value: unknown, path: string): void {
  if (value !== null) number(value, path);
}

function text(value: unknown, path: string): string {
  if (typeof value !== 'string') fail(path, 'not a string');
  return value as string;
}

function flag(value: unknown, path: string): void {
  if (typeof value !== 'boolean') fail(path, 'not true or false');
}

const STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
function stamp(value: unknown, path: string): void {
  if (!STAMP.test(text(value, path))) fail(path, 'not a UTC time');
}

function list(value: unknown, path: string, length?: number): unknown[] {
  if (!Array.isArray(value)) fail(path, 'not a list');
  const items = value as unknown[];
  if (length !== undefined && items.length !== length)
    fail(path, `${items.length} values, not ${length}`);
  return items;
}

function series(value: unknown, path: string, length: number, nullable: boolean): void {
  list(value, path, length).forEach((item, i) =>
    nullable ? maybeNumber(item, `${path}[${i}]`) : number(item, `${path}[${i}]`)
  );
}

function header(value: unknown, name: string): Obj {
  const file = object(value, name);
  const schema = text(file.schema, `${name}.schema`);
  if (schema !== `${name}/1`) fail(`${name}.schema`, `${schema} is not ${name}/1`);
  text(file.license, `${name}.license`);
  stamp(file.generated_at, `${name}.generated_at`);
  return file;
}

function metar(value: unknown, path: string): void {
  if (value === null) return;
  const m = object(value, path);
  text(m.icao, `${path}.icao`);
  text(m.name, `${path}.name`);
  number(m.distance_km, `${path}.distance_km`);
  stamp(m.observed_at, `${path}.observed_at`);
  for (const key of [
    'temperature_c',
    'dew_point_c',
    'wind_kmh',
    'wind_dir_deg',
    'gust_kmh',
    'visibility_m'
  ]) {
    maybeNumber(m[key], `${path}.${key}`);
  }
  if (m.weather !== null) text(m.weather, `${path}.weather`);
  number(m.stale_after_min, `${path}.stale_after_min`);
  for (const key of ['raw', 'cloud_cover']) {
    if (m[key] !== undefined && m[key] !== null) text(m[key], `${path}.${key}`);
  }
}

export function decodeNow(value: unknown): NowFile {
  const file = header(value, 'now');
  text(file.town, 'now.town');
  const reference = object(file.reference, 'now.reference');
  text(reference.name, 'now.reference.name');
  number(reference.distance_km, 'now.reference.distance_km');
  metar(file.metar, 'now.metar');
  if (file.radar !== null) {
    const radar = object(file.radar, 'now.radar');
    stamp(radar.frame_time, 'now.radar.frame_time');
    for (const key of ['rate_mm_h', 'max_5km_mm_h', 'max_10km_mm_h']) {
      maybeNumber(radar[key], `now.radar.${key}`);
    }
    flag(radar.no_data, 'now.radar.no_data');
    number(radar.stale_after_min, 'now.radar.stale_after_min');
  }
  return value as NowFile;
}

function spread(value: unknown, path: string, length: number): void {
  const s = object(value, path);
  flag(s.corrected, `${path}.corrected`);
  for (const key of ['mean', 'low', 'high']) series(s[key], `${path}.${key}`, length, true);
  series(s.m_models, `${path}.m_models`, length, false);
  series(s.lead_band, `${path}.lead_band`, length, false);
}

function consensus(value: unknown, path: string, length: number): void {
  const c = object(value, path);
  flag(c.corrected, `${path}.corrected`);
  series(c.mean, `${path}.mean`, length, true);
}

function rain(value: unknown, path: string, length: number): void {
  const r = object(value, path);
  number(r.threshold_mm, `${path}.threshold_mm`);
  series(r.n_models, `${path}.n_models`, length, false);
  series(r.m_models, `${path}.m_models`, length, false);
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function decodeForecast(value: unknown): ForecastFile {
  const file = header(value, 'forecast');
  text(file.town, 'forecast.town');
  stamp(file.issued_at, 'forecast.issued_at');
  number(file.stale_after_min, 'forecast.stale_after_min');
  number(file.expired_after_min, 'forecast.expired_after_min');
  list(file.models, 'forecast.models').forEach((run, i) => {
    const r = object(run, `forecast.models[${i}]`);
    text(r.model, `forecast.models[${i}].model`);
    stamp(r.run_init, `forecast.models[${i}].run_init`);
  });

  const hourly = object(file.hourly, 'forecast.hourly');
  const hours = list(hourly.time, 'forecast.hourly.time');
  hours.forEach((t, i) => stamp(t, `forecast.hourly.time[${i}]`));
  spread(hourly.temperature_c, 'forecast.hourly.temperature_c', hours.length);
  for (const key of [
    'dew_point_c',
    'wind_kmh',
    'wind_dir_deg',
    'gust_kmh',
    'cloud_pct',
    'precipitation_mm'
  ]) {
    consensus(hourly[key], `forecast.hourly.${key}`, hours.length);
  }
  rain(hourly.rain, 'forecast.hourly.rain', hours.length);

  const daily = object(file.daily, 'forecast.daily');
  const days = list(daily.day, 'forecast.daily.day');
  days.forEach((d, i) => {
    if (!DATE.test(text(d, `forecast.daily.day[${i}]`)))
      fail(`forecast.daily.day[${i}]`, 'not a date');
  });
  spread(daily.tmax_c, 'forecast.daily.tmax_c', days.length);
  spread(daily.tmin_c, 'forecast.daily.tmin_c', days.length);
  rain(daily.rain, 'forecast.daily.rain', days.length);
  for (const key of ['cloud_pct', 'precipitation_mm', 'wind_max_kmh', 'gust_max_kmh']) {
    if (daily[key] !== undefined) consensus(daily[key], `forecast.daily.${key}`, days.length);
  }
  return value as ForecastFile;
}

// The sprite is fetched next to radar.json, so its name must stay a plain file name.
const FILE_NAME = /^[\w.-]+$/;

export function decodeRadar(value: unknown): RadarFile {
  const file = header(value, 'radar');
  text(file.town, 'radar.town');
  if (file.encoding !== 'class-grey9/1')
    fail('radar.encoding', `${String(file.encoding)} is unknown`);
  if (!FILE_NAME.test(text(file.sprite, 'radar.sprite'))) fail('radar.sprite', 'not a file name');
  for (const key of ['frame_width_px', 'frame_height_px', 'columns', 'km_per_px']) {
    if (number(file[key], `radar.${key}`) <= 0) fail(`radar.${key}`, 'not positive');
  }
  list(file.frames, 'radar.frames').forEach((item, i) => {
    const frame = object(item, `radar.frames[${i}]`);
    stamp(frame.time, `radar.frames[${i}].time`);
    flag(frame.missing, `radar.frames[${i}].missing`);
    for (const key of ['town_mm_h', 'max_10km_mm_h']) {
      if (frame[key] !== undefined) maybeNumber(frame[key], `radar.frames[${i}].${key}`);
    }
  });
  const view = object(file.view, 'radar.view');
  for (const key of ['west', 'east', 'south', 'north']) number(view[key], `radar.view.${key}`);
  const town = object(file.town_px, 'radar.town_px');
  number(town.x, 'radar.town_px.x');
  number(town.y, 'radar.town_px.y');
  list(file.scale, 'radar.scale', 6).forEach((item, i) => {
    const bin = object(item, `radar.scale[${i}]`);
    if (bin.index !== i + 1) fail(`radar.scale[${i}].index`, 'out of order');
    number(bin.from_mm_h, `radar.scale[${i}].from_mm_h`);
    maybeNumber(bin.to_mm_h, `radar.scale[${i}].to_mm_h`);
  });
  return value as RadarFile;
}

export function decodeStatus(value: unknown): Status {
  const file = header(value, 'status');
  const sources = object(file.sources, 'status.sources');
  for (const [name, item] of Object.entries(sources)) {
    const source = object(item, `status.sources.${name}`);
    for (const key of ['checked_at', 'data_time']) {
      if (source[key] !== null) stamp(source[key], `status.sources.${name}.${key}`);
    }
  }
  return value as Status;
}
