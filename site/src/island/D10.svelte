<script lang="ts">
  // Ten days, one row each: minimum to maximum on one scale shared by every row,
  // with the range between models as lighter wings at both ends, and rain as one
  // dot per model. A row opens to the ranges in numbers and the models' means.
  import { t } from '#lib/copy/t.ts';
  import { daysShown, rawNote } from '#lib/chart/d10.ts';
  import { deg, int, kmh, mm, models } from '#lib/format.ts';
  import { pick } from '#lib/symbols/pick.ts';
  import Sky from '#lib/symbols/Sky.svelte';
  import Icon from '#lib/symbols/Icon.svelte';
  import { dayNumber, localDate, weekdayShort, ymd } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const forecast = $derived(data.forecast.value);
  const daily = $derived(forecast?.daily);
  const DAY = 86_400_000;

  const scale = $derived.by(() => {
    const all = [...(daily?.tmin_c.low ?? []), ...(daily?.tmax_c.high ?? [])].filter(
      (v): v is number => v !== null
    );
    const low = Math.floor(Math.min(...all, 0));
    const high = Math.ceil(Math.max(...all, 1));
    return (v: number) => ((v - low) / (high - low)) * 100;
  });
  // The bars are drawn in their own pixels, so the hatch of days 8-10 keeps
  // 1 px lines; their width is read on the next frame, as every row shares it.
  let barPx = $state(0);
  function bar(node: SVGSVGElement) {
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => (barPx = node.clientWidth));
    });
    observer.observe(node);
    return {
      destroy() {
        cancelAnimationFrame(frame);
        observer.disconnect();
      }
    };
  }
  // A span on the scale in pixels, never thinner than `least` px so a tight range still shows.
  const span = (a: number, b: number, least: number) => {
    const from = (scale(a) / 100) * barPx;
    const width = Math.max(least, ((scale(b) - scale(a)) / 100) * barPx);
    return { x: Math.min(from, barPx - least), width };
  };

  const rows = $derived.by(() => {
    if (!forecast || !daily) return [];
    const issueDay = localDate(ymd(Date.parse(forecast.issued_at)));
    return daysShown(daily).map((k) => {
      const day = daily.day[k] ?? '';
      const at = localDate(day);
      const ahead = Math.round((at - issueDay) / DAY);
      const n = daily.rain.n_models[k] ?? 0;
      const m = daily.rain.m_models[k] ?? 0;
      // No cloud cover, no sky: a symbol would be a forecast nobody made.
      const cloud = daily.cloud_pct?.mean[k];
      const weekday = weekdayShort(at);
      const name =
        ahead === 1
          ? t('d10.tomorrow')
          : `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)} ${dayNumber(at)}`;
      const min = {
        mean: daily.tmin_c.mean[k],
        low: daily.tmin_c.low[k],
        high: daily.tmin_c.high[k]
      };
      const max = {
        mean: daily.tmax_c.mean[k],
        low: daily.tmax_c.low[k],
        high: daily.tmax_c.high[k]
      };
      return {
        day,
        name,
        // Less reliable: the correction comes from a shorter lead than the day's own.
        far: (daily.tmax_c.lead_band[k] ?? 0) < ahead,
        n,
        m,
        sky: cloud == null ? null : pick(cloud, n, m, daily.precipitation_mm?.mean[k], false, true),
        min,
        max,
        said: [
          name,
          `${t('d10.col_min').toLowerCase()} ${deg(min.mean)}`,
          `${t('d10.col_max').toLowerCase()} ${deg(max.mean)}`,
          `${t('d10.col_rain').toLowerCase()} ${models(n, m)}`
        ].join(', '),
        ranges: t('d10.cell_range', {
          min: int(min.mean),
          minlo: int(min.low),
          minhi: int(min.high),
          max: int(max.mean),
          maxlo: int(max.low),
          maxhi: int(max.high)
        }),
        means: [
          daily.precipitation_mm
            ? `${t('d10.col_rain')} ${mm(daily.precipitation_mm.mean[k])}`
            : '',
          daily.wind_max_kmh
            ? `${t('h48.col_wind').toLowerCase()} ${kmh(daily.wind_max_kmh.mean[k])}`
            : '',
          daily.gust_max_kmh ? t('h48.cell_gust', { g: kmh(daily.gust_max_kmh.mean[k]) }) : ''
        ]
          .filter(Boolean)
          .join(', ')
      };
    });
  });
  const note = $derived(daily ? rawNote(daily) : null);
  const raw = $derived(daily ? !daily.tmin_c.corrected && !daily.tmax_c.corrected : false);
  const near = $derived(rows.filter((row) => !row.far));
  const far = $derived(rows.filter((row) => row.far));
  const capitalise = (text: string) => `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
</script>

{#snippet dots(n: number, m: number)}
  <svg class="dots" width={m * 7 - 2} height="5" viewBox="0 0 {m * 7 - 2} 5" aria-hidden="true">
    {#each Array.from({ length: m }, (_, j) => j) as j (j)}
      <circle
        class:wet={j < n}
        data-qa={j < n ? 'rain' : undefined}
        cx={j * 7 + 2.5}
        cy="2.5"
        r={j < n ? 2.5 : 2}
      />
    {/each}
  </svg>
{/snippet}

{#snippet row(r: (typeof rows)[number])}
  {@const both = r.min.mean != null && r.max.mean != null}
  <li class:far={r.far}>
    <details>
      <summary>
        <span class="vh">{r.said}</span>
        <span class="line" aria-hidden="true">
          <span class="day">{r.name}</span>
          <span class="sky">
            {#if r.sky}<Sky sky={r.sky} size={28} />{/if}
          </span>
          <span class="lo">{deg(r.min.mean)}</span>
          <svg class="bar" use:bar viewBox="0 0 {barPx || 1} 12" focusable="false">
            <rect class="track" x="0" y="5" width={barPx} height="2" />
            {#if r.min.low != null && r.min.high != null}
              {@const s = span(r.min.low, r.min.high, 2)}
              <rect class="wing" data-qa="temp-wing" x={s.x} y="1" width={s.width} height="10" />
            {/if}
            {#if r.max.low != null && r.max.high != null}
              {@const s = span(r.max.low, r.max.high, 2)}
              <rect class="wing" data-qa="temp-wing" x={s.x} y="1" width={s.width} height="10" />
            {/if}
            {#if both}
              {@const s = span(r.min.mean ?? 0, r.max.mean ?? 0, 4)}
              <rect class="core" data-qa="temp" x={s.x} y="1" width={s.width} height="10" />
              {#if r.far}
                <rect x={s.x} y="1" width={s.width} height="10" fill="url(#d10-far)" />
              {/if}
            {/if}
          </svg>
          <span class="hi">{deg(r.max.mean)}</span>
          <span class="rain">
            {@render dots(r.n, r.m)}
            {#if r.n}<b>{t('models.of', { n: r.n, m: r.m })}</b>{/if}
          </span>
        </span>
      </summary>
      <div class="more">
        <p>{capitalise(r.ranges)}.</p>
        {#if r.means}<p>{r.means} ({t('d10.details_mean')}).</p>{/if}
      </div>
    </details>
  </li>
{/snippet}

{#if !forecast || !daily}
  {#if data.forecast.problem}
    <p class="note bad"><Icon name="bad" /><span>{t('state.forecast_missing')}</span></p>
  {:else}
    <div class="skel skel-10">{t('state.loading')}</div>
  {/if}
{:else}
  <svg width="0" height="0" aria-hidden="true" focusable="false" class="vh">
    <defs>
      <pattern
        id="d10-far"
        width="4"
        height="4"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <line class="hatch" x1="0.5" y1="0" x2="0.5" y2="4" />
      </pattern>
    </defs>
  </svg>
  {#if note}
    <p class="note info"><Icon name="info" /><span>{t(note)}</span></p>
  {/if}
  <div class="key" aria-hidden="true">
    <span>
      <svg width="48" height="12" viewBox="0 0 48 12" focusable="false">
        <rect class="wing" x="0" y="1" width="10" height="10" />
        <rect class="core" x="10" y="1" width="28" height="10" />
        <rect class="wing" x="38" y="1" width="10" height="10" />
      </svg>
      {t('d10.key_core')}, {t('d10.key_wings')}
    </span>
    <span>{@render dots(1, 1)} {t('d10.key_dot_full')}</span>
    <span>{@render dots(0, 1)} {t('d10.key_dot_empty')}</span>
  </div>
  <div class="days">
    <ul>
      {#each near as r (r.day)}{@render row(r)}{/each}
    </ul>
    {#if far.length}
      <div class="sep">
        <p class="t">{t('d10.less_reliable_h3')}</p>
        <p class="n">
          {t(note ? 'd10.less_reliable_note_raw' : 'd10.less_reliable_note', {
            m: far[0]?.m ?? 0
          })}
        </p>
      </div>
      <ul>
        {#each far as r (r.day)}{@render row(r)}{/each}
      </ul>
    {/if}
  </div>
  <div class="foot">
    <p>{raw ? t('d10.footnote_raw') : t('d10.footnote', { stazione: data.town.station })}</p>
  </div>
{/if}

<style>
  @layer blocks {
    .key {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-1) var(--space-4);
      margin-block-end: var(--space-3);
      font-size: var(--text-xs);
      color: var(--ink-2);
    }
    .key span {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
    }
    .days {
      container: days / inline-size;
    }
    ul {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    li {
      border-block-start: 1px solid var(--rule);
    }
    summary {
      display: block;
      list-style: none;
      cursor: pointer;
    }
    summary::-webkit-details-marker {
      display: none;
    }
    summary:focus-visible {
      outline: 2px solid var(--ink);
      outline-offset: 2px;
    }
    /* One line where the row fits (measured at 21em), two below it, and three
       where even the second line would not fit, as at 200% text on a phone. */
    .line {
      display: grid;
      grid-template-columns: 2.1em minmax(3rem, 1fr) 2.3em;
      grid-template-areas:
        'day day sky'
        'lo bar hi'
        'rain rain rain';
      align-items: center;
      column-gap: var(--space-2);
      row-gap: var(--space-1);
      min-block-size: 3.5rem;
      padding-block: var(--space-2);
      font-size: var(--text-m);
    }
    @container days (min-width: 15em) {
      .line {
        grid-template-columns: 3.9em 1.75rem 2.1em minmax(3rem, 1fr) 2.3em;
        grid-template-areas:
          'day sky lo bar hi'
          '. . rain rain rain';
      }
    }
    @container days (min-width: 21em) {
      .line {
        grid-template-columns: 3.9em 1.75rem 2.1em minmax(4rem, 1fr) 2.3em 4.5em;
        grid-template-areas: 'day sky lo bar hi rain';
      }
      .rain {
        flex-direction: column;
        align-items: flex-end;
      }
    }
    .day {
      grid-area: day;
      font-weight: 600;
      line-height: 1.15;
    }
    .sky {
      grid-area: sky;
      display: flex;
      justify-content: end;
    }
    @container days (min-width: 15em) {
      .sky {
        justify-content: start;
      }
    }
    .lo {
      grid-area: lo;
      text-align: end;
      color: var(--ink-2);
    }
    .hi {
      grid-area: hi;
      font-weight: 600;
    }
    .bar {
      grid-area: bar;
      inline-size: 100%;
      block-size: 0.75rem;
    }
    .rain {
      grid-area: rain;
      display: flex;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--text-xs);
      line-height: 1.2;
    }
    .track {
      fill: var(--rule);
    }
    .wing {
      fill: var(--temp-wing);
    }
    .core {
      fill: var(--temp);
    }
    .hatch {
      stroke: var(--paper);
      stroke-width: 1;
    }
    .dots circle {
      fill: none;
      stroke: var(--ink-3);
      stroke-width: 1;
    }
    .dots circle.wet {
      fill: var(--rain);
      stroke: none;
    }
    .far .day,
    .far .lo,
    .far .hi {
      color: var(--ink-2);
    }
    .more {
      padding-block-end: var(--space-3);
      font-size: var(--text-s);
      color: var(--ink-2);
    }
    .more p {
      margin: 0;
    }
    .sep {
      padding-block: var(--space-4) var(--space-2);
      border-block-start: 1px solid var(--ink);
    }
    .sep p {
      margin: 0;
    }
    .sep .t {
      font-family: var(--font-serif);
      font-style: italic;
      font-size: var(--text-l);
    }
    .sep .n {
      font-size: var(--text-s);
      color: var(--ink-2);
    }
    .foot {
      margin-block-start: var(--space-3);
      border-block-start: 1px solid var(--rule);
      padding-block-start: var(--space-2);
      font-size: var(--text-s);
      color: var(--ink-2);
    }
    .foot p {
      margin: 0;
    }
  }
</style>
