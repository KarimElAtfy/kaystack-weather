<script lang="ts">
  // The 48 hours as one stack: days, sky, the corrected temperature with the
  // range between models, the models that give rain, wind, and how many models
  // are behind each hour. Hours sit at their UTC time, so the night the clocks
  // go back is 25 hours wide.
  import { t } from '#lib/copy/t.ts';
  import { deg, int } from '#lib/format.ts';
  import { labels } from '#lib/chart/extremes.ts';
  import { lastFullHour } from '#lib/chart/h48.ts';
  import {
    every,
    keep,
    longest,
    overlap,
    rows,
    symbolSize,
    type Box
  } from '#lib/chart/meteogram.ts';
  import { pick } from '#lib/symbols/pick.ts';
  import {
    HOUR_MS,
    dayName,
    dayNumber,
    hm,
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
    selected: number | null;
    readout: string[] | null;
  };
  let { hourly, first, now, lat, lon, selected = $bindable(), readout }: Props = $props();

  let width = $state(0);
  let capHeight = $state(0);
  let root = $state<HTMLElement>();
  // The chart's own text size, read from the page so that it follows the user's setting.
  // A probe ten em wide reports any change of the text size, zoom included.
  let probeWidth = $state(130);
  const font = $derived(probeWidth / 10 || 13);
  let family = $state('sans-serif');
  $effect(() => {
    if (root) family = getComputedStyle(root).fontFamily;
  });
  let context: CanvasRenderingContext2D | null = null;
  const measure = (text: string, bold = false) => {
    context ??= document.createElement('canvas').getContext('2d');
    if (!context) return text.length * font;
    context.font = `${bold ? 600 : 400} ${font}px ${family}`;
    return context.measureText(text).width;
  };

  const times = $derived(hourly.time.map(Date.parse));
  const shown = $derived(times.map((_, i) => i).filter((i) => i >= first));
  const at = (i: number) => times[i] ?? 0;
  const W = $derived(Math.max(200, width));
  const R = $derived(rows(W, font, capHeight || null));
  const lane = (name: keyof typeof R) => (R[name] as [number, number] | undefined) ?? null;

  // The right margin holds the temperature scale, so its labels never sit on the line.
  const plot = $derived(W - 2 - Math.ceil(measure('-10°')) - 6);
  const g = $derived.by(() => {
    const t0 = at(first);
    const t1 = at(times.length - 1);
    const X = (ms: number) => 1 + ((ms - t0) / (t1 - t0)) * plot;
    const perHour = plot / ((t1 - t0) / HOUR_MS);
    const [top, bottom] = lane('temp')!;
    const T = hourly.temperature_c;
    const values = shown
      .flatMap((i) => [T.low[i], T.high[i]])
      .filter((v): v is number => v != null);
    // Room above the band for the highs' labels and below it for the lows'.
    const pad = ((font * 1.6) / (bottom - top)) * (Math.max(...values) - Math.min(...values) || 1);
    const low = Math.min(...values) - pad;
    const high = Math.max(...values) + pad;
    const YT = (v: number) => bottom - ((v - low) / (high - low)) * (bottom - top);
    return { t0, t1, X, perHour, low, high, YT };
  });

  // Gridlines every 5 degrees, labelled every 5 or, where those would touch, every 10.
  const grid = $derived(
    [-15, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40].filter((v) => v > g.low && v < g.high)
  );
  const labelStep = $derived(g.YT(0) - g.YT(5) >= font * 1.3 ? 5 : 10);

  const nights = $derived.by(() => {
    const spans: [number, number][] = [];
    let start: number | null = null;
    for (let k = 0; k <= shown.length; k++) {
      const i = shown[k];
      const dark = i !== undefined && isNight(at(i), lat, lon);
      if (dark && start === null) start = k === 0 ? g.t0 : at(i!) - HOUR_MS / 2;
      if (!dark && start !== null) {
        spans.push([start, i === undefined ? g.t1 : at(i) - HOUR_MS / 2]);
        start = null;
      }
    }
    return spans;
  });

  const midnights = $derived(shown.filter((i) => i > first && ymd(at(i)) !== ymd(at(i - 1))));
  const days = $derived.by(() => {
    const starts = [first, ...midnights];
    return starts.map((i, k) => {
      const end = starts[k + 1] !== undefined ? at(starts[k + 1]!) : g.t1;
      const room = g.X(end) - g.X(at(i));
      const name =
        k === 0
          ? dayName(at(i), now)
          : `${weekdayLong(at(i))} ${dayNumber(at(i))}|${weekdayShort(at(i))} ${dayNumber(at(i))}|${weekdayShort(at(i))}`;
      return { i, x: g.X(at(i)), label: longest(name.split('|'), room, (s) => measure(s, true)) };
    });
  });

  // Steps from the widest label each lane writes.
  const hourStep = $derived(Math.max(3, every(g.perHour, measure('00'))));
  const windStep = $derived(Math.max(3, every(g.perHour, measure('88'))));
  const skyStep = $derived(Math.max(3, every(g.perHour, symbolSize(font), 4)));
  const ticks = $derived(
    shown.filter(
      (i) =>
        i > first &&
        Number(hour(at(i))) % hourStep === 0 &&
        repeatedHour(times, i) !== 'winter' &&
        g.X(at(i)) - measure('00') / 2 > measure(t('h48.axis_now')) + 8 &&
        g.X(at(i)) + measure('00') / 2 < W
    )
  );
  const changes = $derived(shown.filter((i) => repeatedHour(times, i) === 'winter'));

  const skies = $derived.by(() => {
    const out: { x: number; base: string; drops: string | null }[] = [];
    for (let k = 0; k + skyStep <= shown.length - 1; k += skyStep) {
      const block = shown.slice(k + 1, k + skyStep + 1);
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
      const mid = at(shown[k]!) + (skyStep / 2) * HOUR_MS;
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
  const point = (i: number, v: number | null | undefined) =>
    `${g.X(at(i)).toFixed(1)},${g.YT(v ?? 0).toFixed(1)}`;

  // Each day's high and each night's low, as the line draws them, with the hour.
  const marks = $derived.by(() => {
    const T = hourly.temperature_c;
    const placed = labels(hourly, now).map((label) => {
      const text = `${deg(label.value)} ${t('h48.label_at', { ora: String(Number(hour(at(label.i)))) })}`;
      const w = measure(text, true);
      const x = Math.min(plot + 1 - w / 2, Math.max(w / 2 + 2, g.X(at(label.i))));
      const y =
        label.kind === 'high'
          ? g.YT(T.high[label.i] ?? label.value) - 5
          : g.YT(T.low[label.i] ?? label.value) + font + 3;
      const box: Box = { left: x - w / 2, right: x + w / 2, top: y - font, bottom: y + 3 };
      return { text, x, y, box };
    });
    // A label wider than the plot has no place on it: left out, never shrunk.
    const [top, bottom] = lane('temp')!;
    return keep(
      placed.filter(
        (mark) =>
          mark.box.right - mark.box.left <= plot &&
          mark.box.top >= top &&
          mark.box.bottom <= bottom + 2
      )
    );
  });
  const dayBoxes = $derived.by(() => {
    const [top, bottom] = lane('day')!;
    return days.flatMap((d) => {
      if (!d.label) return [];
      const left = d.i === first ? 0 : d.x + 4;
      return [{ left, right: left + measure(d.label, true), top, bottom: bottom + font * 0.3 }];
    });
  });
  // The clock change is said above the chart too, so its mark gives way to the labels.
  const dstMarks = $derived.by(() => {
    const [top] = lane('temp')!;
    const text = t('h48.dst_marker');
    const w = measure(text);
    return changes
      .map((i) => {
        const x = g.X(at(i)) + 3;
        return { x, box: { left: x, right: x + w, top, bottom: top + font + 3 } };
      })
      .filter(
        (m) =>
          m.box.right <= W &&
          ![...marks.map((other) => other.box), ...dayBoxes].some((other) => overlap(other, m.box))
      );
  });
  // The lane titles shorten to one word where the long one would not fit.
  const title = (long: string, short: string) =>
    longest([long, short], W + 8, (s) => measure(s, true)) ?? short;

  const [rainTop, rainBottom] = $derived(lane('rain') ?? [0, 0]);
  // Bars stop a line short of the lane's top, so the count above the tallest stays inside.
  const barTop = $derived(rainTop + Math.ceil(font * 1.4));
  const rainShare = (i: number) => (hourly.rain.n_models[i] ?? 0) / (hourly.rain.m_models[i] || 1);
  const wet = $derived(shown.filter((i) => (hourly.rain.n_models[i] ?? 0) > 0));
  const wettest = $derived(
    wet.length ? wet.reduce((a, b) => (rainShare(b) > rainShare(a) ? b : a)) : null
  );
  const barWidth = $derived(Math.max(2, Math.min(12, g.perHour - 1.5)));

  const winds = $derived(
    shown.filter((i) => {
      const x = g.X(at(i));
      const half = measure('88') / 2;
      return (
        Number(hour(at(i))) % windStep === 0 &&
        repeatedHour(times, i) !== 'winter' &&
        hourly.wind_kmh.mean[i] != null &&
        x - half >= 0 &&
        x + half <= W
      );
    })
  );

  // How many models stand behind each hour: a line that thins where they run out.
  const M = $derived(hourly.temperature_c.m_models);
  const steps = $derived(shown.filter((i, k) => k === 0 || M[i] !== M[shown[k - 1]!]));
  const lastFull = $derived(lastFullHour(hourly));
  const modelsText = $derived(
    steps.length > 1
      ? t('h48.models_line', {
          m: M[first] ?? 0,
          ora1: `${dayName(at(lastFull), now)} ${t('time.at', { ora: hm(at(lastFull)) })}`,
          k: M.at(-1) ?? 0
        })
      : ''
  );

  function choose(event: PointerEvent) {
    if (event.type === 'pointermove' && event.pointerType !== 'mouse' && !event.buttons) return;
    const box = (event.currentTarget as SVGSVGElement).getBoundingClientRect();
    const ms = g.t0 + ((event.clientX - box.left - 1) / plot) * (g.t1 - g.t0);
    let best = first;
    for (const i of shown) if (Math.abs(at(i) - ms) < Math.abs(at(best) - ms)) best = i;
    selected = best;
  }
  // The chart's width, the screen's height cap and the text size, read on the
  // next frame: drawing in the observer's own turn makes WebKit report a loop.
  function sizes(node: HTMLElement) {
    const cap = node.querySelector<HTMLElement>('.cap')!;
    const probe = node.querySelector<HTMLElement>('.probe')!;
    let frame = 0;
    const read = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        width = node.clientWidth;
        capHeight = cap.clientHeight;
        probeWidth = probe.clientWidth;
      });
    };
    const observer = new ResizeObserver(read);
    for (const target of [node, cap, probe]) observer.observe(target);
    return {
      destroy() {
        cancelAnimationFrame(frame);
        observer.disconnect();
      }
    };
  }
  // The readout stays until Escape, a tap outside the chart, or another hour.
  $effect(() => {
    if (selected === null) return;
    const outside = (event: PointerEvent) => {
      if (root && !root.contains(event.target as Node)) selected = null;
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') selected = null;
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  });
  // Over the day and sky rows, beside the chosen hour; set through the CSSOM,
  // which the policy allows where a style attribute would be refused.
  function beside(node: HTMLElement, x: number) {
    const move = (x: number) => {
      const room = root?.clientWidth ?? 0;
      node.style.left = `${Math.max(0, Math.min(room - node.offsetWidth, x - node.offsetWidth / 2))}px`;
    };
    move(x);
    return { update: move };
  }
</script>

<div class="meteogram" bind:this={root} use:sizes>
  <div class="cap" aria-hidden="true"></div>
  <div class="probe" aria-hidden="true"></div>
  {#if readout && selected !== null}
    <div class="readout" use:beside={g.X(at(selected))}>
      {#each readout as line, k (k)}<p class:when={k === 0}>{line}</p>{/each}
    </div>
  {/if}
  {#if width}
    {@const day = lane('day')!}
    {@const sky = lane('sky')}
    {@const temp = lane('temp')!}
    {@const wind = lane('wind')!}
    {@const arrows = lane('arrows')}
    {@const axis = lane('axis')!}
    {@const models = lane('models')!}
    {@const plotTop = sky ? sky[0] : temp[0]}
    <svg
      width={W}
      height={R.height}
      viewBox="0 0 {W} {R.height}"
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
          data-qa="night"
          x={g.X(a)}
          y={plotTop}
          width={g.X(z) - g.X(a)}
          height={wind[1] - plotTop}
        />
      {/each}
      {#each grid as v (v)}
        <line class="grid" class:zero={v === 0} x1="0" x2={W} y1={g.YT(v)} y2={g.YT(v)} />
        {#if v % labelStep === 0}
          <text class="ylab" x={W - 2} y={g.YT(v) - 3} text-anchor="end">{int(v)}°</text>
        {/if}
      {/each}
      {#each midnights as i (i)}
        <line class="mid" x1={g.X(at(i))} x2={g.X(at(i))} y1={day[0]} y2={axis[0]} />
      {/each}
      {#each days as d (d.i)}
        {#if d.label}
          <text class="day" x={d.i === first ? 0 : d.x + 4} y={day[1] - 5}>{d.label}</text>
        {/if}
      {/each}
      {#if sky}
        {@const size = symbolSize(font)}
        {#each skies as s (s.x)}
          <svg
            x={s.x - size / 2}
            y={sky[0] + 3}
            width={size}
            height={size}
            viewBox="0 0 32 32"
            data-qa="sym-ink"
          >
            <use href="#{s.base}" />
            {#if s.drops}<use href="#{s.drops}" />{/if}
          </svg>
        {/each}
      {/if}
      {#each changes as i (i)}
        <line class="dst" x1={g.X(at(i))} x2={g.X(at(i))} y1={temp[0]} y2={wind[1]} />
      {/each}
      {#each dstMarks as mark (mark.x)}
        <text class="note" x={mark.x} y={mark.box.bottom - 3}>{t('h48.dst_marker')}</text>
      {/each}
      {#each segments as segment (segment[0])}
        <polygon
          class="band"
          data-qa="temp-band"
          points={[
            ...segment.map((i) => point(i, hourly.temperature_c.high[i])),
            ...segment.toReversed().map((i) => point(i, hourly.temperature_c.low[i]))
          ].join(' ')}
        />
        <polyline
          class="temp"
          data-qa="temp"
          points={segment.map((i) => point(i, hourly.temperature_c.mean[i])).join(' ')}
        />
      {/each}
      {#each segments.slice(1) as segment, k (segment[0])}
        {@const from = g.X(at(segments[k]?.at(-1) ?? first))}
        <rect
          x={from}
          y={temp[0]}
          width={g.X(at(segment[0] ?? first)) - from}
          height={temp[1] - temp[0]}
          fill="url(#gap)"
        />
      {/each}
      {#each marks as mark (mark.text + mark.x)}
        <text class="mark" x={mark.x} y={mark.y} text-anchor="middle">{mark.text}</text>
      {/each}

      <text class="title" x="0" y={lane('rainTitle')![1] - 5}
        >{title(t('h48.panel_rain'), t('h48.col_rain'))}</text
      >
      <line class="base" x1="0" x2={W} y1={rainBottom} y2={rainBottom} />
      {#if wettest === null}
        <text class="none" x={W / 2} y={(rainTop + rainBottom) / 2 + font / 3} text-anchor="middle"
          >{t('rain48.none')}</text
        >
      {:else}
        <line
          class="half"
          x1="0"
          x2={W}
          y1={(barTop + rainBottom) / 2}
          y2={(barTop + rainBottom) / 2}
        />
        {#each wet as i (i)}
          {@const h = rainShare(i) * (rainBottom - barTop)}
          <rect
            class="rbar"
            data-qa="rain"
            x={Math.max(0, g.X(at(i)) - barWidth)}
            y={rainBottom - h}
            width={Math.min(barWidth, g.X(at(i)))}
            height={h}
          />
        {/each}
        {@const text = t('models.of', {
          n: hourly.rain.n_models[wettest] ?? 0,
          m: hourly.rain.m_models[wettest] ?? 0
        })}
        {@const half = measure(text, true) / 2 + 2}
        <text
          class="mark"
          x={Math.min(W - half, Math.max(half, g.X(at(wettest)) - barWidth / 2))}
          y={rainBottom - rainShare(wettest) * (rainBottom - barTop) - 4}
          text-anchor="middle">{text}</text
        >
      {/if}

      <text class="title" x="0" y={lane('windTitle')![1] - 5}
        >{title(t('h48.panel_wind'), t('h48.col_wind'))}</text
      >
      {#each winds as i (i)}
        {@const v = hourly.wind_kmh.mean[i] ?? 0}
        {#if arrows && v >= 3 && hourly.wind_dir_deg.mean[i] != null}
          <path
            class="arrow"
            transform="translate({g.X(at(i)).toFixed(1)} {(arrows[0] + arrows[1]) /
              2}) rotate({((hourly.wind_dir_deg.mean[i] ?? 0) + 180) % 360})"
            d="M0 -5.5 L3.4 3 L0 1.1 L-3.4 3 Z"
          />
        {/if}
        <text class="wv" x={g.X(at(i))} y={wind[1] - 3} text-anchor="middle">{int(v)}</text>
      {/each}

      <text class="now" x="0" y={axis[1] - 5}>{t('h48.axis_now')}</text>
      {#each ticks as i (i)}
        <text x={g.X(at(i))} y={axis[1] - 5} text-anchor="middle">{hour(at(i))}</text>
      {/each}
      {#each steps as i, k (i)}
        {@const x2 = steps[k + 1] !== undefined ? g.X(at(steps[k + 1]!)) : W}
        <line
          class="mline"
          stroke-width={1 + ((M[i] ?? 0) / (M[first] || 1)) * 2}
          x1={g.X(at(i)) + (k ? 1 : 0)}
          x2={x2 - 1}
          y1={models[0] + 4}
          y2={models[0] + 4}
        />
      {/each}

      {#if selected !== null}
        <g pointer-events="none">
          <line
            class="cross"
            x1={g.X(at(selected))}
            x2={g.X(at(selected))}
            y1={plotTop}
            y2={wind[1]}
          />
          {#if hourly.temperature_c.mean[selected] != null}
            <circle
              class="dot"
              r="4.5"
              cx={g.X(at(selected))}
              cy={g.YT(hourly.temperature_c.mean[selected] ?? 0)}
            />
          {/if}
        </g>
      {/if}
    </svg>
    {#if modelsText}<p class="models">{modelsText}</p>{/if}
  {/if}
</div>

<style>
  @layer blocks {
    /* Its height before the first frame measures it, from the lanes H48 sets on
       the block, so the range and the note under it never move. */
    .meteogram {
      position: relative;
      min-block-size: calc(
        max(
            6 * var(--line) + var(--plot-min),
            min(80svh, 6 * var(--line) + var(--icon) + var(--plot))
          ) +
          var(--models-lines) * 1.5 * var(--text-xs)
      );
      font-size: var(--text-xs);
      touch-action: pan-y;
    }
    .probe {
      position: absolute;
      inline-size: 10em;
      visibility: hidden;
      pointer-events: none;
    }
    .models {
      margin: 0;
      color: var(--ink-2);
    }
    .cap {
      position: absolute;
      inset-inline: 0;
      block-size: 80svh;
      visibility: hidden;
      pointer-events: none;
    }
    svg {
      display: block;
      overflow: visible;
    }
    text {
      font-size: var(--text-xs);
      font-family: var(--font-sans);
      fill: var(--ink-2);
    }
    .day,
    .mark {
      font-weight: 600;
      fill: var(--ink);
    }
    .mark,
    .ylab {
      paint-order: stroke;
      stroke: var(--paper);
      stroke-width: 3px;
      stroke-linejoin: round;
    }
    .title,
    .now {
      font-weight: 600;
    }
    .none {
      fill: var(--ink-2);
    }
    .grid {
      stroke: var(--rule);
    }
    .grid.zero {
      stroke: var(--ink-3);
    }
    .mid,
    .dst {
      stroke: var(--rule);
    }
    .dst {
      stroke-dasharray: 3 3;
    }
    .night {
      fill: var(--night);
    }
    .hatch {
      stroke: var(--rule);
      stroke-width: 2;
    }
    .band {
      fill: var(--temp-band);
      stroke: var(--temp);
      stroke-width: 1;
      stroke-opacity: 0.5;
    }
    .temp {
      fill: none;
      stroke: var(--temp);
      stroke-width: 2.5;
      stroke-linejoin: round;
      stroke-linecap: round;
    }
    .base {
      stroke: var(--ink-3);
    }
    .rbar {
      fill: var(--rain);
    }
    .half {
      stroke: var(--ink-3);
      stroke-dasharray: 2 3;
    }
    .arrow {
      fill: var(--ink-2);
    }
    .mline {
      stroke: var(--ink-3);
      stroke-linecap: round;
    }
    .cross {
      stroke: var(--ink);
      stroke-width: 1.25;
    }
    .dot {
      fill: var(--temp);
      stroke: var(--paper);
      stroke-width: 2;
    }
    .readout {
      position: absolute;
      inset-block-start: 0;
      z-index: 1;
      max-inline-size: min(22rem, 100%);
      padding: var(--space-2) var(--space-3);
      background: var(--paper);
      border: 1px solid var(--ink);
      font-size: var(--text-s);
      line-height: 1.35;
    }
    .readout p {
      margin: 0;
    }
    .readout .when {
      font-weight: 600;
    }
  }
</style>
