// Which symbol a block of hours, a day or a METAR gets. Only states the data
// supports: cloud in four classes, rain from how many models agree, and fog,
// thunder and snow from the METAR in Adesso only.

export type Sky = {
  // Sprite ids: the sky, then the drops drawn under it.
  base: string;
  drops: string | null;
  // The copy key under sky.* that names the symbol.
  key: string;
};

const RAIN_LIGHT = { hourly: [1, 4], daily: [5, 20] };

export function pick(
  cloudPct: number | null | undefined,
  rainy: number,
  models: number,
  mm: number | null | undefined,
  night: boolean,
  daily: boolean
): Sky {
  const share = models ? rainy / models : 0;
  let base =
    cloudPct === null || cloudPct === undefined
      ? 'cloudy'
      : cloudPct < 20
        ? 'clear'
        : cloudPct < 55
          ? 'few'
          : cloudPct < 90
            ? 'cloudy'
            : 'overcast';
  let drops = 0;
  // At least half the models: drops counted by the mean amount. A fifth: possible.
  if (share >= 0.5) {
    const [one, two] = daily ? RAIN_LIGHT.daily : RAIN_LIGHT.hourly;
    drops = mm === null || mm === undefined || mm < (one ?? 0) ? 1 : mm < (two ?? 0) ? 2 : 3;
  }
  const maybe = !drops && share >= 0.2;
  const wet = drops > 0 || maybe;
  if (wet && base === 'clear') base = 'few';
  const sky = base === 'clear' || base === 'few' ? `${base}-${night ? 'night' : 'day'}` : base;
  return {
    base: wet ? `${sky}-wet` : sky,
    drops: drops ? `drops-${drops}` : maybe ? 'drops-maybe' : null,
    key: drops ? `rain_${drops}` : maybe ? 'rain_maybe' : sky.replace('-', '_')
  };
}

export function fromMetar(weather: string | null | undefined): Sky | null {
  if (!weather) return null;
  if (/TS/.test(weather)) return { base: 'thunder', drops: null, key: 'thunder' };
  if (/SN|SG/.test(weather)) return { base: 'snow', drops: null, key: 'snow' };
  if (/RA|DZ/.test(weather)) {
    const drops = /\+/.test(weather) ? 3 : /-/.test(weather) ? 1 : 2;
    return { base: 'overcast-wet', drops: `drops-${drops}`, key: `rain_${drops}` };
  }
  if (/FG/.test(weather)) return { base: 'fog', drops: null, key: 'fog' };
  return null;
}

export function fromCover(code: string | null | undefined, night: boolean): Sky | null {
  if (!code) return null;
  const time = night ? 'night' : 'day';
  if (/^(CAVOK|NSC|SKC|CLR|NCD)$/.test(code))
    return { base: `clear-${time}`, drops: null, key: `clear_${time}` };
  if (/^(FEW|SCT)$/.test(code)) return { base: `few-${time}`, drops: null, key: `few_${time}` };
  if (code === 'BKN') return { base: 'cloudy', drops: null, key: 'cloudy' };
  return { base: 'overcast', drops: null, key: 'overcast' };
}
