// Writes the hand-made public files under tests/fixtures/<scenario>/, laid out
// like the public container, until recorded ones replace them at launch. The
// weather is the design prototype's: Saturday 24 October 2026 at 15:10 in Rome,
// so the 48 hours cross the end of summer time. Run with node scripts/fixtures.ts.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { deflateSync, crc32 } from 'node:zlib';

const H = 3_600_000;
const MIN = 60_000;
const NOW = Date.parse('2026-10-24T13:10:00Z');
const ISSUE = Date.parse('2026-10-24T12:00:00Z');
const N = 120;

const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z');
const r1 = (x: number) => Math.round(x * 10) / 10;
const clamp = (x: number, a: number, b: number) => Math.max(a, Math.min(b, x));

function random(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Local hour in Rome: summer time until 25 October 01:00 UTC.
const romeHour = (ms: number) =>
  (new Date(ms).getUTCHours() + (ms < Date.parse('2026-10-25T01:00:00Z') ? 2 : 1)) % 24;

function diurnal(ms: number, low: number, high: number) {
  const h = romeHour(ms) + new Date(ms).getUTCMinutes() / 60;
  const x = Math.cos(((h - 15) / 24) * 2 * Math.PI);
  const shaped = h >= 7 && h <= 15 ? Math.sin((((h - 7) / 8) * Math.PI) / 2) : (x + 1) / 2;
  return low + (high - low) * clamp(shaped, 0, 1);
}

type Town = {
  slug: string;
  reference: { name: string; distance_km: number };
  airport: { icao: string; name: string; distance_km: number };
  view: { west: number; east: number; south: number; north: number };
  town: [number, number];
  seed: number;
  warmer: number;
};

// Station, airport and grid as in towns/*.toml; distances by haversine.
const TOWNS: Town[] = [
  {
    slug: 'pedrengo',
    reference: { name: 'Torre Boldone', distance_km: 3.4 },
    airport: { icao: 'LIME', name: 'Bergamo Orio al Serio', distance_km: 4.3 },
    view: { west: -275000, east: -155000, south: 354000, north: 474000 },
    town: [60, 60],
    seed: 11,
    warmer: 0
  },
  {
    slug: 'sesto-calende',
    reference: { name: 'Ispra JRC', distance_km: 9.1 },
    airport: { icao: 'LIMC', name: 'Milano Malpensa', distance_km: 12.5 },
    view: { west: -361000, east: -241000, south: 371000, north: 491000 },
    town: [60, 70],
    seed: 23,
    warmer: 0.7
  }
];

type Weather = {
  // Per day from the issue day: min, max, rainy models, rain mm, cloud %.
  days: [number, number, number, number, number][];
  rain: (t: number, lead: number) => number;
  amount: (share: number, t: number) => number;
  cloud: (share: number, t: number, ms: number) => number;
  wind: (t: number) => { v: number; d: number; g: number };
  metar: {
    t: number;
    td: number;
    v: number;
    d: number | null;
    vis: number;
    wx: string | null;
    cover: string;
    raw: string;
  };
  front: boolean;
};

// A cold front on Saturday evening, showers on Sunday, clearing on Monday.
const RAINY: Weather = {
  days: [
    [9, 16, 10, 22, 100],
    [9, 13, 7, 6, 80],
    [7, 14, 1, 0.4, 35],
    [5, 15, 0, 0, 15],
    [6, 16, 1, 0.3, 30],
    [8, 14, 3, 5, 85],
    [9, 13, 3, 7, 90],
    [7, 14, 1, 1, 60],
    [6, 13, 2, 2, 70],
    [5, 12, 0, 0, 40],
    [4, 12, 0, 0, 30]
  ],
  rain: (t) =>
    clamp(Math.exp(-(((t - 8) / 4.5) ** 2)) + 0.45 * Math.exp(-(((t - 26) / 3.5) ** 2)), 0, 1),
  amount: (share, t) => (share > 0.5 ? share * (t < 14 ? 3.6 : 1.2) : share * 0.3),
  cloud: (share, t) =>
    t < 20 ? 100 : t < 34 ? 70 + 25 * share : clamp(45 - (t - 34) * 3, 10, 100),
  wind: (t) => ({
    v: t < 14 ? 12 + t * 0.7 : t < 24 ? 14 - (t - 14) * 0.5 : 8 - (t - 24) * 0.12,
    d: t < 12 ? 215 : t < 20 ? 260 : 20,
    g: t < 14 ? 1.9 : 1.6
  }),
  metar: {
    t: 13,
    td: 11,
    v: 15,
    d: 210,
    vis: 6000,
    wx: '-RA BR',
    cover: 'OVC',
    raw: 'LIME 241250Z 21008KT 6000 -RA BR FEW008 BKN015 OVC030 13/11 Q1009'
  },
  front: true
};

// High pressure, sunny afternoons, fog on Sunday morning.
const DRY: Weather = {
  days: [
    [8, 18, 0, 0, 10],
    [8, 19, 0, 0, 30],
    [7, 18, 0, 0, 20],
    [6, 17, 0, 0, 25],
    [7, 16, 1, 0.2, 45],
    [9, 15, 2, 1.5, 75],
    [9, 13, 3, 4, 85],
    [8, 12, 2, 3, 80],
    [6, 12, 1, 0.5, 55],
    [5, 13, 0, 0, 30],
    [6, 14, 1, 0.5, 50]
  ],
  rain: (_t, lead) => (lead > 40 ? 0.12 : 0),
  amount: (share) => share * 0.1,
  cloud: (_share, t, ms) => {
    const h = romeHour(ms);
    return t > 14 && t < 24 && h >= 5 && h <= 10 ? 100 : 8 + 6 * Math.sin(t / 5);
  },
  wind: (t) => ({ v: 6 + 2 * Math.sin(t / 4), d: 90 + 40 * Math.sin(t / 7), g: 1.7 }),
  metar: {
    t: 17,
    td: 8,
    v: 6,
    d: null,
    vis: 9999,
    wx: null,
    cover: 'FEW',
    raw: 'LIME 241250Z VRB03KT 9999 FEW040 17/08 Q1027'
  },
  front: false
};

// Models that reach each lead, from the issue at 12 UTC.
const modelsAt = (lead: number) => (lead <= 33 ? 10 : lead <= 42 ? 9 : 8);
const MODELS_BY_DAY = [9, 7, 6, 6, 5, 4, 4, 3, 3, 3];

type Options = {
  issuedAt: number;
  radarAt: number;
  metarAt: number;
  gap: boolean;
  thin: boolean;
  partial: boolean;
  noRadar: boolean;
  missingFrame: boolean;
  extras: boolean;
};

function forecast(town: Town, w: Weather, o: Options) {
  const rnd = random(town.seed + (w.front ? 1 : 2));
  const time: string[] = [];
  const mean: (number | null)[] = [];
  const low: (number | null)[] = [];
  const high: (number | null)[] = [];
  const spreadModels: number[] = [];
  const band: number[] = [];
  const dew: number[] = [],
    speed: number[] = [],
    direction: number[] = [],
    gust: number[] = [],
    cloud: number[] = [],
    precip: number[] = [],
    rainy: number[] = [],
    counted: number[] = [];
  for (let lead = 0; lead <= 48; lead++) {
    const ms = o.issuedAt + lead * H;
    const t = (ms - ISSUE) / H;
    time.push(iso(ms));
    const local = romeHour(ms);
    const day = t < 10 ? 0 : t < 35 ? 1 : 2;
    const [tmin, tmax] = w.days[day]!;
    const nextMin = w.days[Math.min(day + 1, 10)]![0];
    let T =
      diurnal(ms, local >= 15 ? nextMin : tmin, tmax) +
      town.warmer * (local < 9 || local > 19 ? 1 : 0.3);
    if (w.front) T -= 2.2 * Math.exp(-(((t - 9) / 3) ** 2));
    const m = modelsAt(lead);
    const spread = 0.7 + 0.055 * lead + (w.front ? 1.2 * Math.exp(-(((t - 8) / 3) ** 2)) : 0);
    const skew = (rnd() - 0.5) * 0.6;
    const tm = r1(T);
    mean.push(tm);
    low.push(r1(tm - spread * (0.55 + skew * 0.3) - 0.1));
    high.push(r1(tm + spread * (0.45 - skew * 0.3) + 0.1));
    spreadModels.push(m);
    // The oldest run in the mean started at 00 UTC, twelve hours before the issue.
    band.push(Math.min(Math.floor((lead + 12) / 24), 7));
    dew.push(r1(T - (w.front ? 1.6 + (t > 20 ? 2 : 0) : 7 + 3 * Math.sin(t / 6))));
    const share = w.rain(t, lead);
    const n = Math.round(share * m + (share > 0.05 && share < 0.95 ? rnd() - 0.5 : 0));
    rainy.push(clamp(n, 0, m));
    counted.push(m);
    precip.push(r1(Math.max(0, w.amount(share, t))));
    cloud.push(Math.round(clamp(w.cloud(share, t, ms), 0, 100)));
    const wind = w.wind(t);
    const v = Math.max(1, wind.v + (rnd() - 0.5) * 2);
    speed.push(r1(v));
    direction.push(Math.round(((wind.d % 360) + 360) % 360));
    gust.push(r1(v * wind.g + rnd() * 3));
  }
  if (o.gap) {
    // No corrected model for these hours: the contract writes nulls, never raw values.
    for (let i = 30; i <= 33; i++) {
      mean[i] = low[i] = high[i] = null;
      spreadModels[i] = 0;
    }
  }

  const days: string[] = [];
  const tmaxMean: number[] = [],
    tmaxLow: number[] = [],
    tmaxHigh: number[] = [],
    tminMean: number[] = [],
    tminLow: number[] = [],
    tminHigh: number[] = [];
  const dayRainy: number[] = [],
    dayCounted: number[] = [],
    dayBand: number[] = [],
    dayCloud: number[] = [],
    dayPrecip: number[] = [],
    dayWind: number[] = [],
    dayGust: number[] = [];
  for (let d = 1; d <= 10; d++) {
    days.push(new Date(Date.parse('2026-10-24T10:00:00Z') + d * 24 * H).toISOString().slice(0, 10));
    const [tmin, tmax, rainN, rainMm, cl] = w.days[d]!;
    const m = o.thin && d === 10 ? 2 : MODELS_BY_DAY[d - 1]!;
    const width = 0.8 + 0.35 * d + (d >= 8 ? 0.8 : 0);
    const a = (rnd() - 0.5) * 0.4;
    const shift = town.warmer > 0 ? 1 : 0;
    tminMean.push(tmin + shift);
    tminLow.push(r1(tmin + shift - width * (0.5 + a)));
    tminHigh.push(r1(tmin + shift + width * (0.5 - a)));
    tmaxMean.push(tmax - shift);
    tmaxLow.push(r1(tmax - shift - width * (0.5 - a)));
    tmaxHigh.push(r1(tmax - shift + width * (0.5 + a)));
    dayRainy.push(Math.min(Math.round((rainN / 10) * m), m));
    dayCounted.push(m);
    dayBand.push(Math.min(d, 7));
    dayCloud.push(cl);
    dayPrecip.push(rainMm);
    dayWind.push(w.front && d === 1 ? 20 : 9 + (d % 3) * 2);
    dayGust.push(w.front && d === 1 ? 41 : 20 + (d % 4) * 3);
  }
  const spread = (m: number[], lo: number[], hi: number[], models: number[]) => ({
    corrected: true,
    mean: m,
    low: lo,
    high: hi,
    m_models: models,
    lead_band: dayBand.slice()
  });
  const runs: [string, string][] = [
    ['ecmwf_ifs', '2026-10-24T00:00:00Z'],
    ['ecmwf_aifs025_single', '2026-10-24T00:00:00Z'],
    ['icon_d2', '2026-10-24T09:00:00Z'],
    ['icon_eu', '2026-10-24T06:00:00Z'],
    ['italia_meteo_arpae_icon_2i', '2026-10-24T00:00:00Z'],
    ['meteoswiss_icon_ch1', '2026-10-24T09:00:00Z'],
    ['meteoswiss_icon_ch2', '2026-10-24T06:00:00Z'],
    ['meteofrance_arome_france_hd', '2026-10-24T06:00:00Z'],
    ['ukmo_global_deterministic_10km', '2026-10-24T00:00:00Z'],
    ['gfs_global', '2026-10-24T06:00:00Z']
  ];
  const daily: Record<string, unknown> = {
    day: days,
    tmax_c: spread(tmaxMean, tmaxLow, tmaxHigh, dayCounted.slice()),
    tmin_c: spread(tminMean, tminLow, tminHigh, dayCounted.slice()),
    rain: { threshold_mm: 1.0, n_models: dayRainy, m_models: dayCounted }
  };
  if (o.extras) {
    // Requested additions to v1 (SITE-SPEC B1), so the 10-day symbols can be seen.
    daily.cloud_pct = { corrected: false, mean: dayCloud };
    daily.precipitation_mm = { corrected: false, mean: dayPrecip };
    daily.wind_max_kmh = { corrected: false, mean: dayWind };
    daily.gust_max_kmh = { corrected: false, mean: dayGust };
  }
  return {
    schema: 'forecast/1',
    license: 'CC BY-SA 4.0',
    attribution: 'Open-Meteo.com (CC BY 4.0)',
    generated_at: iso(o.issuedAt + 4 * MIN),
    town: town.slug,
    issued_at: iso(o.issuedAt),
    method: 'mean60-v1',
    models: runs.map(([model, run_init]) => ({ model, run_init })),
    stale_after_min: 180,
    expired_after_min: 1440,
    hourly: {
      time,
      temperature_c: { corrected: true, mean, low, high, m_models: spreadModels, lead_band: band },
      dew_point_c: { corrected: false, mean: dew },
      wind_kmh: { corrected: false, mean: speed },
      wind_dir_deg: { corrected: false, mean: direction },
      gust_kmh: { corrected: false, mean: gust },
      cloud_pct: { corrected: false, mean: cloud },
      precipitation_mm: { corrected: false, mean: precip },
      rain: { threshold_mm: 0.2, n_models: rainy, m_models: counted }
    },
    daily
  };
}

// Rain rates per cell, NaN where the radar sees nothing.
function frames(town: Town, w: Weather, last: number, count: number) {
  const [tx, ty] = town.town;
  const rnd = random(town.slug === 'pedrengo' ? 5 : 9);
  const L = 16;
  const lattice = Array.from({ length: (L + 2) * (L + 2) }, () => rnd());
  const noise = (x: number, y: number) => {
    const gx = (x / N) * L;
    const gy = (y / N) * L;
    const x0 = Math.floor(gx);
    const y0 = Math.floor(gy);
    const v = (i: number, j: number) => lattice[(j % (L + 2)) * (L + 2) + (i % (L + 2))] ?? 0;
    const sx = (gx - x0) ** 2 * (3 - 2 * (gx - x0));
    const sy = (gy - y0) ** 2 * (3 - 2 * (gy - y0));
    return (
      (v(x0, y0) * (1 - sx) + v(x0 + 1, y0) * sx) * (1 - sy) +
      (v(x0, y0 + 1) * (1 - sx) + v(x0 + 1, y0 + 1) * sx) * sy
    );
  };
  const sesto = town.slug === 'sesto-calende';
  return Array.from({ length: count }, (_, k) => {
    const field = new Float32Array(N * N);
    const shift = (k - (count - 1)) * 2.4;
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        // A sector the radar beam does not reach.
        const blocked = sesto ? y < 26 - x * 0.18 && x < 70 : y < 14 && x > 78 + y * 1.2;
        if (blocked) {
          field[y * N + x] = NaN;
          continue;
        }
        let v = 0;
        if (w.front) {
          const across = (x - tx) * 0.94 + (y - ty) * 0.34 - shift + (sesto ? 6 : 0);
          const bandShape = Math.exp(-(((across + 12) / 9) ** 2));
          const edge = across < 2 ? 1 : Math.exp(-(across - 2) / 1.5);
          const cell = Math.exp(-((x - tx + 20 - shift) ** 2 + (y - ty - 12) ** 2) / 30) * 22;
          v =
            (bandShape * (0.6 + 10 * noise(x - shift * 0.9, y + shift * 0.3) ** 2.2) + cell) * edge;
          if (v < 0.25) v = 0;
          const shower =
            Math.exp(-((x - tx - 30) ** 2 + (y - ty + 25) ** 2) / 18) *
            3.2 *
            (0.6 + 0.4 * Math.sin(k / 2));
          if (shower > 0.3) v = Math.max(v, shower);
        }
        field[y * N + x] = v;
      }
    }
    return { time: last - (count - 1 - k) * 5 * MIN, field };
  });
}

const BOUNDS = [0.2, 1, 2, 6, 15, 40];
const classOf = (v: number) => BOUNDS.filter((b) => v >= b).length;

// Rate at the town, and the highest within 5 and 10 km, as the pipeline computes them.
function atTown(field: Float32Array, town: Town) {
  const [tx, ty] = town.town;
  let five = 0;
  let ten = 0;
  for (let y = ty - 10; y <= ty + 10; y++) {
    for (let x = tx - 10; x <= tx + 10; x++) {
      const d2 = (x - tx) ** 2 + (y - ty) ** 2;
      const v = field[y * N + x] ?? NaN;
      if (Number.isNaN(v) || d2 > 100) continue;
      ten = Math.max(ten, v);
      if (d2 <= 25) five = Math.max(five, v);
    }
  }
  const here = field[ty * N + tx] ?? NaN;
  return { here: Number.isNaN(here) ? null : r1(here), five: r1(five), ten: r1(ten) };
}

// Grey plus alpha PNG. The pipeline writes WebP; the site decodes both the same way.
function png(width: number, height: number, pixels: Uint8Array): Buffer {
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const out = Buffer.alloc(body.length + 8);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(crc32(body), body.length + 4);
    return out;
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 4, 0, 0, 0], 8);
  const rows = Buffer.alloc((width * 2 + 1) * height);
  for (let y = 0; y < height; y++) {
    pixels
      .subarray(y * width * 2, (y + 1) * width * 2)
      .forEach((b, i) => (rows[y * (width * 2 + 1) + 1 + i] = b));
  }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(rows, { level: 9 })),
    chunk('IEND', Buffer.alloc(0))
  ]);
}

function sprite(list: { field: Float32Array; missing: boolean }[], columns: number) {
  const rows = Math.ceil(list.length / columns);
  const width = columns * N;
  const pixels = new Uint8Array(width * rows * N * 2);
  list.forEach(({ field, missing }, k) => {
    const ox = (k % columns) * N;
    const oy = Math.floor(k / columns) * N;
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        const v = field[y * N + x] ?? NaN;
        const index = missing || Number.isNaN(v) ? ((x + y) % 4 === 0 ? 7 : 8) : classOf(v);
        const at = ((oy + y) * width + ox + x) * 2;
        pixels[at] = Math.round((255 * (index + 0.5)) / 9);
        pixels[at + 1] = index === 0 ? 0 : 255;
      }
    }
  });
  return png(width, rows * N, pixels);
}

function scenario(name: string, w: Weather, o: Options) {
  const root = join('tests/fixtures', name);
  // Only this scenario's folder: tests/fixtures also holds the stand-in maps.
  rmSync(root, { recursive: true, force: true });
  const write = (path: string, body: unknown) => {
    mkdirSync(join(root, path, '..'), { recursive: true });
    writeFileSync(
      join(root, path),
      typeof body === 'string' || Buffer.isBuffer(body)
        ? body
        : `${JSON.stringify(body, null, 1)}\n`
    );
  };
  for (const town of TOWNS) {
    const sesto = town.slug === 'sesto-calende';
    const list = frames(town, w, o.radarAt, 12).map((f, k) => ({
      ...f,
      missing: o.missingFrame && k === 7
    }));
    const latest = atTown(list[list.length - 1]!.field, town);
    const m = w.metar;
    const metar = {
      icao: town.airport.icao,
      name: town.airport.name,
      distance_km: town.airport.distance_km,
      observed_at: iso(o.metarAt),
      temperature_c: m.t + (sesto ? 1 : 0),
      dew_point_c: o.partial ? null : m.td,
      wind_kmh: m.v,
      wind_dir_deg: m.d,
      gust_kmh: w.front && sesto && !o.partial ? 32 : null,
      visibility_m: o.partial ? null : m.vis,
      weather: w.front && sesto ? '-SHRA' : m.wx,
      stale_after_min: 90,
      ...(o.extras ? { raw: m.raw.replace('LIME', town.airport.icao), cloud_cover: m.cover } : {})
    };
    write(`v1/${town.slug}/now.json`, {
      schema: 'now/1',
      license: 'CC BY-SA 4.0',
      attribution: 'Radar-DPC (CC BY-SA 4.0); METAR: NOAA Aviation Weather Center',
      generated_at: iso(Math.max(o.metarAt, o.radarAt) + MIN),
      town: town.slug,
      reference: town.reference,
      metar,
      radar: o.noRadar
        ? null
        : {
            frame_time: iso(o.radarAt),
            rate_mm_h: latest.here,
            max_5km_mm_h: latest.five,
            max_10km_mm_h: latest.ten,
            no_data: latest.here === null,
            stale_after_min: 15
          }
    });
    write(`v1/${town.slug}/forecast.json`, forecast(town, w, o));
    if (o.noRadar) continue;
    const name = `radar-${iso(o.radarAt).replace(/[-:]/g, '').slice(0, 13)}.png`;
    write(`v1/${town.slug}/${name}`, sprite(list, 4));
    write(`v1/${town.slug}/radar.json`, {
      schema: 'radar/1',
      license: 'CC BY-SA 4.0',
      attribution: 'Radar-DPC (CC BY-SA 4.0)',
      generated_at: iso(o.radarAt + 90_000),
      town: town.slug,
      encoding: 'class-grey9/1',
      sprite: name,
      frame_width_px: N,
      frame_height_px: N,
      columns: 4,
      frames: list.map((f) => ({
        time: iso(f.time),
        missing: f.missing,
        // Requested addition to v1 (SITE-SPEC B3), for the sentence under the map.
        ...(o.extras && !f.missing
          ? { town_mm_h: atTown(f.field, town).here, max_10km_mm_h: atTown(f.field, town).ten }
          : {})
      })),
      view: town.view,
      km_per_px: 1,
      town_px: { x: town.town[0], y: town.town[1] },
      scale: BOUNDS.map((from, i) => ({
        index: i + 1,
        from_mm_h: from,
        to_mm_h: BOUNDS[i + 1] ?? null
      }))
    });
  }
  const source = (checked: number, data: number) => ({
    checked_at: iso(checked),
    data_time: iso(data),
    parts: {}
  });
  write('status.json', {
    schema: 'status/1',
    license: 'CC BY-SA 4.0',
    attribution: 'Open-Meteo.com, Radar-DPC, NOAA Aviation Weather Center, ARPA Lombardia',
    generated_at: iso(NOW - MIN),
    sources: {
      metar: source(NOW - 3 * MIN, o.metarAt),
      radar: source(o.noRadar ? NOW - 2 * MIN : o.radarAt + 2 * MIN, o.radarAt),
      'open-meteo': source(o.issuedAt === ISSUE ? NOW - 25 * MIN : NOW - 7 * H, o.issuedAt - 3 * H),
      arpa: source(NOW - 90 * MIN, NOW - 7 * H - 50 * MIN)
    }
  });
}

const base: Options = {
  issuedAt: ISSUE,
  radarAt: NOW - 5 * MIN,
  metarAt: NOW - 20 * MIN,
  gap: false,
  thin: false,
  partial: false,
  noRadar: false,
  missingFrame: false,
  extras: true
};

scenario('pioggia', RAINY, base);
scenario('asciutto', DRY, base);
scenario('vecchi', RAINY, {
  ...base,
  metarAt: NOW - 170 * MIN,
  radarAt: NOW - 50 * MIN,
  issuedAt: Date.parse('2026-10-24T05:00:00Z'),
  missingFrame: true
});
scenario('mancanti', RAINY, {
  ...base,
  partial: true,
  noRadar: true,
  radarAt: NOW - 3 * H,
  gap: true,
  thin: true,
  extras: false
});
