<script lang="ts">
  // The hero under the town line, in three parts the page lays out: .now (what
  // was measured), .next (what the models say about the next 12 hours) and
  // .details. Each part waits for its own file, so a missing forecast never
  // hides the measurement, nor the other way round.
  import { around, has, t } from '#lib/copy/t.ts';
  import {
    deg,
    directionLong,
    humidity,
    int,
    km,
    kmh,
    mmh,
    pct,
    point,
    temp,
    visibility,
    weather
  } from '#lib/format.ts';
  import { pair } from '#lib/chart/extremes.ts';
  import { strip, verdict } from '#lib/data/ahead.ts';
  import { forecastFreshness, metarFreshness, radarAtTownFreshness } from '#lib/data/states.ts';
  import { classOf, className } from '#lib/radar/classes.ts';
  import { fromCover, fromMetar } from '#lib/symbols/pick.ts';
  import Sky from '#lib/symbols/Sky.svelte';
  import Icon from '#lib/symbols/Icon.svelte';
  import { skyName } from '#lib/symbols/words.ts';
  import { ago, hm, isNight } from '#lib/time.ts';
  import Next12 from './Next12.svelte';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  // Under the radar's lightest class, 0,2 mm/h, it is not raining.
  const RAIN = 0.2;
  // Visibility is worth a word only when it is poor.
  const POOR_VISIBILITY_M = 5000;

  const file = $derived(data.now.value);
  const metar = $derived(file?.metar ?? null);
  const radar = $derived(file?.radar ?? null);
  const metarState = $derived(metar ? metarFreshness(metar, data.clock) : null);

  const sky = $derived.by(() => {
    if (!metar) return null;
    const night = isNight(data.clock, data.town.lat, data.town.lon);
    return fromMetar(metar.weather) ?? fromCover(metar.cloud_cover, night);
  });
  // The name people use; an airport without one in the copy keeps the METAR's.
  const airport = (m: { icao: string; name: string }) => {
    const key = `airport.${m.icao}`;
    return has(key) ? t(key) : m.name;
  };
  const cover = (code: string | null | undefined) => {
    const key = `metar.cover.${code}`;
    return code && has(key) ? t(key) : null;
  };

  const rainLine = $derived.by(() => {
    if (!radar || radarAtTownFreshness(radar, data.clock) === 'expired') return null;
    const at = Date.parse(radar.frame_time);
    const stale = radarAtTownFreshness(radar, data.clock) === 'stale';
    const here = radar.rate_mm_h;
    const near5 = radar.max_5km_mm_h ?? 0;
    const near10 = radar.max_10km_mm_h ?? 0;
    let text: string;
    if (radar.no_data || here === null) text = t('state.radar_nodata_here');
    else if (here >= RAIN) {
      const said = { intensita: className(classOf(here)), valore: mmh(here), ora: hm(at) };
      text = t(stale ? 'now.rain_here_past' : 'now.rain_here', said);
    } else if (stale) text = t('now.rain_none_past', { ora: hm(at) });
    else if (near5 >= RAIN) text = t('now.rain_5', { valore: mmh(near5) });
    else if (near10 >= RAIN) text = t('now.rain_10', { valore: mmh(near10) });
    else text = t('now.rain_none');
    return { text, link: t('now.source_radar', { ora: hm(at), fa: ago(at, data.clock) }) };
  });

  // "Vento 9 km/h da nord, umidità 87%": gusts only when the METAR has them,
  // visibility only when it is poor.
  const detailLine = $derived.by(() => {
    if (!metar) return '';
    const parts: string[] = [];
    const dir = point(metar.wind_dir_deg);
    if (metar.wind_kmh !== null && metar.wind_kmh < 2) parts.push(t('now.line_calm'));
    else if (metar.wind_kmh !== null) {
      const from = dir ? t('wind.from', { dir: directionLong(dir) }) : t('wind.variable');
      parts.push(t('now.line_wind', { v: kmh(metar.wind_kmh), dir: from }));
    }
    if (metar.gust_kmh !== null) parts.push(t('now.line_gust', { g: kmh(metar.gust_kmh) }));
    const rh = humidity(metar.temperature_c, metar.dew_point_c);
    if (rh !== null) parts.push(t('now.line_humidity', { pct: pct(rh) }));
    if (metar.visibility_m !== null && metar.visibility_m < POOR_VISIBILITY_M) {
      parts.push(t('now.line_vis', { v: visibility(metar.visibility_m) }));
    }
    const line = parts.join(', ');
    return line.charAt(0).toUpperCase() + line.slice(1);
  });

  const forecast = $derived(data.forecast.value);
  // A forecast past its expiry says nothing about the next 12 hours.
  const usable = $derived(forecast && forecastFreshness(forecast, data.clock) !== 'expired');
  const sentence = $derived(usable && forecast ? verdict(forecast.hourly, data.clock) : '');
  const figures = $derived(
    usable && forecast ? pair(forecast, data.clock).filter((f) => f.value !== null) : []
  );
  const cells = $derived(
    usable && forecast ? strip(forecast.hourly, data.clock, data.town.lat, data.town.lon) : []
  );
  const figure = (word: string, value: number | null) =>
    around(`verdict.${word}` as 'verdict.today', 't', { t: deg(value) });
</script>

<div class="now">
  {#if !file && !data.now.problem}
    <p class="wait">{t('state.loading')}</p>
  {:else}
    {#if !metar}
      <p class="alert bad"><Icon name="bad" /><span>{t('state.metar_missing')}</span></p>
    {:else}
      {@const at = Date.parse(metar.observed_at)}
      {@const source = t('now.source_metar', {
        aeroporto: airport(metar),
        km: km(metar.distance_km),
        ora: hm(at),
        fa: ago(at, data.clock)
      })}
      {#if metarState === 'expired'}
        <p class="alert">
          <Icon name="warn" /><span>{t('state.metar_expired', { ora: hm(at) })}</span>
        </p>
      {:else}
        <div class="hero" class:stale={metarState === 'stale'}>
          <p class="temp" data-qa="temperature">
            {#if metar.temperature_c === null}
              {t('state.nodata')}
            {:else}
              <span class="vh">{t('now.temp_label')}: {temp(metar.temperature_c)}</span>
              <span aria-hidden="true">{int(metar.temperature_c)}<span class="deg">°</span></span>
            {/if}
          </p>
          <p class="sky">
            {#if sky}<Sky {sky} size={40} label={skyName(sky)} />{/if}
            <span
              >{weather(metar.weather) ?? cover(metar.cloud_cover) ?? t('now.weather_none')}</span
            >
          </p>
        </div>
      {/if}
      <!-- A late bulletin says so on its own source line, which carries its age. -->
      <p class="source" class:late={metarState === 'stale'}>
        {source}{#if metarState === 'stale'}
          <strong>{t('state.stale_tag')}</strong>{/if}
      </p>
    {/if}
    <p class="rain" data-qa="rain-line">
      {#if rainLine}
        {rainLine.text}
        <a href="#radar">{rainLine.link}</a>
      {:else}
        {t('state.radar_missing')}
        <a href="#radar">{t('radar.h2')}</a>
      {/if}
    </p>
  {/if}
</div>

<div class="next">
  {#if usable}
    <p class="verdict" data-qa="verdict">{sentence}</p>
    {#if figures.length}
      <p class="pair" data-qa="pair">
        {#each figures as f (f.word)}
          {@const [before, after] = figure(f.word, f.value)}
          <span>{before}<b>{deg(f.value)}</b>{after}</span>{' '}
        {/each}
      </p>
    {/if}
    {#if cells.length}<Next12 {cells} />{/if}
  {:else if !forecast && !data.forecast.problem}
    <p class="wait">{t('state.loading')}</p>
  {:else}
    <p class="alert">{t('state.forecast_missing')}</p>
  {/if}
</div>

{#if metar && metarState !== 'expired'}
  <div class="details" class:stale={metarState === 'stale'}>
    <p>{detailLine}</p>
    {#if metar.raw}
      <details>
        <summary>{t('now.metar_raw')}</summary>
        {#if metar.dew_point_c !== null}
          <p>{t('now.dewpoint')} {temp(metar.dew_point_c)}</p>
        {/if}
        <code>{metar.raw}</code>
      </details>
    {/if}
  </div>
{/if}

<style>
  @layer blocks {
    .now,
    .next,
    .details {
      min-inline-size: 0;
    }
    /* The parts hold about their loaded height while they wait, and the page's
       placeholder holds the first, so the arrival of a file moves little. In
       rem, so a larger text size grows the room with the text. The figures
       are for one column on a phone, where a late bulletin and Linux's wider
       fonts take the source line to three lines. */
    .now {
      min-block-size: 18.5rem;
    }
    .next {
      min-block-size: 15rem;
    }
    .details {
      min-block-size: 4.25rem;
    }
    /* In one column the page's placeholder stands for all three parts. */
    :global(#adesso-body.skel-now) {
      min-block-size: calc(37.75rem + 2 * var(--space-4));
    }
    /* Under 21em the lines wrap more and the strip takes two rows. */
    @container hero (width < 21em) {
      .now {
        min-block-size: 20rem;
      }
      .next {
        min-block-size: 23.75rem;
      }
      :global(#adesso-body.skel-now) {
        min-block-size: calc(48rem + 2 * var(--space-4));
      }
    }
    /* In two columns the lines are long and the placeholder holds the left one. */
    @container hero (width >= 40em) {
      .now,
      :global(#adesso-body.skel-now) {
        min-block-size: 15.5rem;
      }
      .next {
        min-block-size: 17rem;
      }
    }
    /* The sky always under the figure: beside it, it jumped to the next line
       whenever the figure grew, and left a hole where it had been. */
    .hero {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: var(--space-2);
      margin-block: var(--space-2) var(--space-3);
    }
    /* The tight line height sets the figures close to the words; the padding
       gives back the font's own height, which would otherwise reach into the
       lines above and below it. */
    .temp {
      font-size: var(--text-hero);
      font-weight: 600;
      line-height: 0.82;
      letter-spacing: -0.055em;
      padding-block: 0.2em;
    }
    .deg {
      font-weight: 300;
      color: var(--ink-3);
    }
    @container hero (width < 24em) {
      .temp {
        font-size: 4.5rem;
      }
    }
    .sky {
      display: flex;
      flex-wrap: nowrap;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--text-l);
      color: var(--ink-2);
    }
    .source,
    .details {
      font-size: var(--text-s);
      color: var(--ink-2);
    }
    .rain {
      margin-block-start: var(--space-2);
    }
    .stale {
      color: var(--ink-3);
    }
    .late {
      color: var(--warn);
      border-inline-start: 2px solid var(--warn);
      padding-inline-start: var(--space-2);
    }
    .late strong {
      font-weight: 600;
    }
    .alert {
      display: flex;
      gap: var(--space-2);
      align-items: baseline;
      color: var(--warn);
      border-inline-start: 2px solid var(--warn);
      padding-inline-start: var(--space-2);
      margin-block: var(--space-2);
    }
    .alert.bad {
      color: var(--bad);
      border-color: var(--bad);
    }
    .wait {
      color: var(--ink-2);
    }
    /* Sans, because it carries numbers: the serif's last fallback, Georgia,
       has old-style figures. */
    .verdict {
      margin-block-start: var(--space-5);
      font-size: var(--text-l);
      line-height: 1.3;
    }
    .next {
      padding-block-end: var(--space-4);
    }
    .pair {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-1) var(--space-5);
      margin-block: var(--space-2) var(--space-4);
      font-size: var(--text-l);
    }
    .pair span {
      color: var(--ink-2);
    }
    .pair b {
      color: var(--ink);
      font-weight: 600;
    }
    summary {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      min-block-size: var(--tap);
      padding-inline: var(--space-3);
      border: 1px solid var(--ink-3);
      cursor: pointer;
      color: var(--ink);
      list-style: none;
    }
    summary::-webkit-details-marker {
      display: none;
    }
    summary::before {
      content: '';
      inline-size: 0.45em;
      block-size: 0.45em;
      border-inline-end: 2px solid currentColor;
      border-block-end: 2px solid currentColor;
      transform: rotate(-45deg);
    }
    details[open] summary::before {
      transform: rotate(45deg);
    }
    code {
      display: block;
      overflow-wrap: anywhere;
      font-size: var(--text-xs);
      color: var(--ink);
    }
  }
</style>
