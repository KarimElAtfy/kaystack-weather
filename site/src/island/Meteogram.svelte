<script lang="ts">
  // The 48 hours as one SVG: temperature with the range between models, the
  // share of models with rain, and wind. Hours sit at their UTC time, so the
  // night the clocks go back is 25 hours wide.
  import { ICONS } from '#gen/icons.ts';
  import { t } from '#lib/copy/t.ts';
  import { int } from '#lib/format.ts';
  import { niceStep } from '#lib/chart/h48.ts';
  import { pick } from '#lib/symbols/pick.ts';
  import {
    HOUR_MS,
    dayNumber,
    hour,
    isNight,
    repeatedHour,
    weekdayLong,
    weekdayShort,
    ymd
  } from '#lib/time.ts';
  import type { ForecastFile } from '#lib/data/decode.ts';

  type Props = {
    hourly: ForecastFile['hourly'];
    first: number;
    now: number;
    lat: number;
    lon: number;
    selected: number;
  };
  let { hourly, first, now, lat, lon, selected = $bindable() }: Props = $props();

  let width = $state(0);
  const W = $derived(Math.max(280, width));
  const times = $derived(hourly.time.map(Date.parse));
  const shown = $derived(times.map((_, i) => i).filter((i) => i >= first));
  const narrow = $derived(W < 560);
  const left = 32;
  const right = 8;
  const at = (i: number) => times[i] ?? 0;

  const g = $derived.by(() => {
    const plot = W - left - right;
    const t0 = at(first);
    const t1 = at(times.length - 1);
    const X = (ms: number) => left + ((ms - t0) / (t1 - t0)) * plot;
    const perHour = plot / ((t1 - t0) / HOUR_MS);
    const top = 20;
    const symbols = narrow ? 30 : 34;
    const tempTop = top + symbols + 18;
    const tempHeight = narrow ? 124 : 168;
    const rainTop = tempTop + tempHeight + 26;
    const rainHeight = narrow ? 46 : 62;
    const windTop = rainTop + rainHeight + 40;
    const windHeight = narrow ? 60 : 82;
    const axis = windTop + windHeight;
    const temps = shown
      .flatMap((i) => [hourly.temperature_c.low[i], hourly.temperature_c.high[i]])
      .filter((v): v is number => v !== null && v !== undefined);
    let low = Math.floor(Math.min(...temps, 10) - 1);
    let high = Math.ceil(Math.max(...temps, 0) + 1);
    const tempStep = niceStep(high - low, narrow ? 3 : 4);
    low = Math.floor(low / tempStep) * tempStep;
    high = Math.ceil(high / tempStep) * tempStep;
    const YT = (v: number) => tempTop + tempHeight - ((v - low) / (high - low)) * tempHeight;
    const gusts = Math.max(...shown.map((i) => hourly.gust_kmh.mean[i] ?? 0), 10);
    const windMax = Math.ceil((gusts + 4) / 10) * 10;
    const YW = (v: number) => windTop + windHeight - (v / windMax) * windHeight;
    return {
      plot,
      t0,
      t1,
      X,
      perHour,
      top,
      symbols,
      tempTop,
      tempHeight,
      rainTop,
      rainHeight,
      windTop,
      windHeight,
      axis,
      H: axis + 22,
      low,
      high,
      tempStep,
      YT,
      windMax,
      YW
    };
  });

  const range = (a: number, b: number, step: number) =>
    Array.from({ length: Math.floor((b - a) / step + 1e-9) + 1 }, (_, k) => a + k * step);
  const panels = $derived([
    [g.tempTop, g.tempTop + g.tempHeight],
    [g.rainTop, g.rainTop + g.rainHeight],
    [g.windTop - 18, g.axis]
  ] as [number, number][]);

  const nights = $derived.by(() => {
    const spans: [number, number][] = [];
    let start: number | null = null;
    for (let k = 0; k <= shown.length; k++) {
      const i = shown[k];
      const night = i !== undefined && isNight(at(i), lat, lon);
      if (night && start === null) start = k === 0 ? g.t0 : at(i!) - HOUR_MS / 2;
      if (!night && start !== null) {
        spans.push([start, i === undefined ? g.t1 : at(i) - HOUR_MS / 2]);
        start = null;
      }
    }
    return spans;
  });

  const days = $derived.by(() => {
    const bounds = [g.t0];
    for (const i of shown) if (i > first && ymd(at(i)) !== ymd(at(i - 1))) bounds.push(at(i));
    bounds.push(g.t1);
    return bounds.slice(0, -1).map((a, k) => {
      const z = bounds[k + 1] ?? g.t1;
      const mid = a + (z - a) / 2;
      const room = g.X(z) - g.X(a);
      const long = `${weekdayLong(mid)} ${dayNumber(mid)}`;
      const short = `${weekdayShort(mid)} ${dayNumber(mid)}`;
      const weekday = weekdayShort(mid);
      const label =
        [long, short, weekday].find((text, i) => room > text.length * 7 + (i ? 6 : 12)) ?? '';
      return { a, separator: k > 0, x: g.X(mid), label };
    });
  });

  const every = $derived(g.perHour * 3 >= 34 ? 3 : 6);
  const ticks = $derived(
    shown.filter((i) => Number(hour(at(i))) % every === 0 && repeatedHour(times, i) !== 'winter')
  );
  const changes = $derived(shown.filter((i) => repeatedHour(times, i) === 'winter'));

  const symbolStep = $derived(g.perHour * 3 >= 30 ? 3 : 6);
  const symbolSize = $derived(Math.min(26, Math.max(20, g.perHour * symbolStep - 6)));
  const symbols = $derived.by(() => {
    const out: { x: number; base: string; drops: string | null }[] = [];
    for (let k = 0; k + symbolStep <= shown.length; k += symbolStep) {
      const block = shown.slice(k + 1, k + symbolStep + 1);
      const clouds = block
        .map((i) => hourly.cloud_pct.mean[i])
        .filter((v): v is number => v != null);
      const cloud = clouds.length ? clouds.reduce((a, b) => a + b, 0) / clouds.length : null;
      let n = 0;
      let m = 1;
      let mm = 0;
      for (const i of block) {
        const bn = hourly.rain.n_models[i] ?? 0;
        const bm = hourly.rain.m_models[i] ?? 0;
        if (bm && bn / bm > n / m) [n, m] = [bn, bm];
        mm = Math.max(mm, hourly.precipitation_mm.mean[i] ?? 0);
      }
      const mid = at(shown[k] ?? first) + (symbolStep / 2) * HOUR_MS;
      const sky = pick(cloud, n, m, mm, isNight(mid, lat, lon), false);
      out.push({ x: g.X(mid), base: sky.base, drops: sky.drops });
    }
    return out;
  });

  // Lines break where no corrected model exists; the gap is hatched.
  const segments = $derived.by(() => {
    const out: number[][] = [];
    let current: number[] = [];
    for (const i of shown) {
      if (hourly.temperature_c.mean[i] == null) {
        if (current.length) out.push(current);
        current = [];
      } else current.push(i);
    }
    if (current.length) out.push(current);
    return out;
  });
  const point = (i: number, v: number | null | undefined, Y: (v: number) => number) =>
    `${g.X(at(i)).toFixed(1)},${Y(v ?? 0).toFixed(1)}`;
  const extremes = $derived.by(() => {
    const valid = shown.filter((i) => hourly.temperature_c.mean[i] != null);
    if (!valid.length) return null;
    const mean = (i: number) => hourly.temperature_c.mean[i] ?? 0;
    return {
      hot: valid.reduce((a, b) => (mean(b) > mean(a) ? b : a)),
      cold: valid.reduce((a, b) => (mean(b) < mean(a) ? b : a))
    };
  });
  const barWidth = $derived(Math.max(2, Math.min(14, g.perHour - 2)));
  const arrows = $derived(
    shown
      .filter((_, k) => k % (g.perHour * 3 >= 22 ? 3 : 6) === 0)
      .filter((i) => (hourly.wind_kmh.mean[i] ?? 0) >= 2 && hourly.wind_dir_deg.mean[i] != null)
  );
  const nowX = $derived(now >= g.t0 && now <= g.t1 ? g.X(now) : null);
  const clamp = (x: number) => Math.min(W - right - 14, Math.max(left + 14, x));

  function choose(event: PointerEvent) {
    if (event.type === 'pointermove' && event.pointerType !== 'mouse' && !event.buttons) return;
    const box = (event.currentTarget as SVGSVGElement).getBoundingClientRect();
    const ms = g.t0 + ((event.clientX - box.left - left) / g.plot) * (g.t1 - g.t0);
    let best = first;
    for (const i of shown) if (Math.abs(at(i) - ms) < Math.abs(at(best) - ms)) best = i;
    selected = best;
  }
</script>

<div class="chart" bind:clientWidth={width}>
  {#if width}
    <svg
      width={W}
      height={g.H}
      viewBox="0 0 {W} {g.H}"
      aria-hidden="true"
      focusable="false"
      onpointerdown={choose}
      onpointermove={choose}
    >
      <defs>
        <pattern
          id="gap"
          width="6"
          height="6"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <line class="hatch" x1="0" y1="0" x2="0" y2="6" />
        </pattern>
      </defs>
      {#each nights as [a, z] (a)}
        <rect
          class="night"
          x={g.X(a)}
          y={g.top + g.symbols}
          width={g.X(z) - g.X(a)}
          height={g.axis - g.top - g.symbols}
        />
      {/each}
      {#each range(g.low, g.high, g.tempStep) as v (v)}
        <line class="grid" x1={left} x2={W - right} y1={g.YT(v)} y2={g.YT(v)} />
        <text x={left - 6} y={g.YT(v) + 4} text-anchor="end">{int(v)}°</text>
      {/each}
      {#if g.low < 0 && g.high > 0}
        <line class="zero" x1={left} x2={W - right} y1={g.YT(0)} y2={g.YT(0)} />
      {/if}
      {#each [0.5, 1] as share (share)}
        {@const y = g.rainTop + g.rainHeight - share * g.rainHeight}
        <line class="grid" x1={left} x2={W - right} y1={y} y2={y} />
        <text x={left - 6} y={y + 4} text-anchor="end"
          >{share === 1 ? t('h48.axis_all') : t('h48.axis_half')}</text
        >
      {/each}
      <line
        class="grid"
        x1={left}
        x2={W - right}
        y1={g.rainTop + g.rainHeight}
        y2={g.rainTop + g.rainHeight}
      />
      {#each range(0, g.windMax, g.windMax > 40 ? 20 : 10) as v (v)}
        <line class="grid" x1={left} x2={W - right} y1={g.YW(v)} y2={g.YW(v)} />
        <text x={left - 6} y={g.YW(v) + 4} text-anchor="end">{v}</text>
      {/each}
      <text class="ptitle" x="0" y={g.tempTop - 8}>{t('h48.panel_temp')}</text>
      <text class="ptitle" x="0" y={g.rainTop - 9}>{t('h48.panel_rain')}</text>
      <text class="ptitle" x="0" y={g.windTop - 25}>{t('h48.panel_wind')}</text>
      {#each days as day (day.a)}
        {#if day.separator}
          {#each [[g.top - 2, g.top + g.symbols], ...panels] as [a, b] (a)}
            <line class="sep" x1={g.X(day.a)} x2={g.X(day.a)} y1={a} y2={b} />
          {/each}
        {/if}
        {#if day.label}<text class="daylab" x={day.x} y={g.top - 6} text-anchor="middle"
            >{day.label}</text
          >{/if}
      {/each}
      {#each ticks as i (i)}
        <line class="sep" x1={g.X(at(i))} x2={g.X(at(i))} y1={g.axis} y2={g.axis + 4} />
        <text x={g.X(at(i))} y={g.axis + 16} text-anchor="middle">{hour(at(i))}</text>
      {/each}
      {#each changes as i (i)}
        {#each panels as [a, b] (a)}
          <line class="dst" x1={g.X(at(i))} x2={g.X(at(i))} y1={a} y2={b} />
        {/each}
        <text class="vlab" x={g.X(at(i)) + 3} y={g.tempTop + 11}>{t('h48.dst_marker')}</text>
      {/each}
      {#each symbols as s (s.x)}
        <svg
          x={s.x - symbolSize / 2}
          y={g.top + 2}
          width={symbolSize}
          height={symbolSize}
          viewBox="0 0 32 32"
        >
          <use href="{ICONS}#{s.base}" />
          {#if s.drops}<use href="{ICONS}#{s.drops}" />{/if}
        </svg>
      {/each}
      {#each segments as segment (segment[0])}
        <polygon
          class="band"
          points={[
            ...segment.map((i) => point(i, hourly.temperature_c.high[i], g.YT)),
            ...segment.toReversed().map((i) => point(i, hourly.temperature_c.low[i], g.YT))
          ].join(' ')}
        />
        <polyline
          class="temp"
          points={segment.map((i) => point(i, hourly.temperature_c.mean[i], g.YT)).join(' ')}
        />
      {/each}
      {#each segments.slice(1) as segment, k (segment[0])}
        {@const from = g.X(at(segments[k]?.at(-1) ?? first))}
        <rect
          x={from}
          y={g.tempTop}
          width={g.X(at(segment[0] ?? first)) - from}
          height={g.tempHeight}
          fill="url(#gap)"
        />
      {/each}
      {#if extremes}
        <text
          class="vlab"
          x={clamp(g.X(at(extremes.hot)))}
          y={g.YT(hourly.temperature_c.high[extremes.hot] ?? 0) - 6}
          text-anchor="middle">{int(hourly.temperature_c.mean[extremes.hot])}°</text
        >
        <text
          class="vlab"
          x={clamp(g.X(at(extremes.cold)))}
          y={g.YT(hourly.temperature_c.low[extremes.cold] ?? 0) + 14}
          text-anchor="middle">{int(hourly.temperature_c.mean[extremes.cold])}°</text
        >
      {/if}
      {#each shown.filter((i) => hourly.rain.n_models[i]) as i (i)}
        {@const share = (hourly.rain.n_models[i] ?? 0) / (hourly.rain.m_models[i] || 1)}
        <rect
          class="rbar"
          class:on={i === selected}
          x={g.X(at(i)) - barWidth}
          width={barWidth}
          y={g.rainTop + g.rainHeight - share * g.rainHeight}
          height={share * g.rainHeight}
          rx="2"
        />
      {/each}
      {#each arrows as i (i)}
        <path
          class="arrow"
          transform="translate({g.X(at(i)).toFixed(1)} {g.windTop - 9}) rotate({((hourly
            .wind_dir_deg.mean[i] ?? 0) +
            180) %
            360})"
          d="M0 -5.5 L3.4 3 L0 1.1 L-3.4 3 Z"
        />
      {/each}
      <polyline
        class="wind"
        points={shown
          .filter((i) => hourly.wind_kmh.mean[i] != null)
          .map((i) => point(i, hourly.wind_kmh.mean[i], g.YW))
          .join(' ')}
      />
      {#each shown.filter((i) => hourly.gust_kmh.mean[i] != null && !(narrow && (i - first) % 2)) as i (i)}
        <circle
          class="gust"
          cx={g.X(at(i))}
          cy={g.YW(hourly.gust_kmh.mean[i] ?? 0)}
          r={narrow ? 1.8 : 2.4}
        />
      {/each}
      {#if nowX !== null}
        {#each panels as [a, b] (a)}<line class="now" x1={nowX} x2={nowX} y1={a} y2={b} />{/each}
      {/if}
      <g pointer-events="none">
        {#each panels as [a, b] (a)}
          <line class="cross" x1={g.X(at(selected))} x2={g.X(at(selected))} y1={a} y2={b} />
        {/each}
        {#if hourly.temperature_c.mean[selected] != null}
          <circle
            class="xt"
            r="4"
            cx={g.X(at(selected))}
            cy={g.YT(hourly.temperature_c.mean[selected] ?? 0)}
          />
        {/if}
        <circle
          class="xw"
          r="4"
          cx={g.X(at(selected))}
          cy={g.YW(hourly.wind_kmh.mean[selected] ?? 0)}
        />
      </g>
    </svg>
  {/if}
</div>
