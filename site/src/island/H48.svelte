<script lang="ts">
  import { t } from '#lib/copy/t.ts';
  import { int, mm, models, pct, temp, wind } from '#lib/format.ts';
  import { firstShown, lastFullHour, nextHour, observed, summary } from '#lib/chart/h48.ts';
  import Icon from '#lib/symbols/Icon.svelte';
  import { dayName, dstLabel, hm, weekdayLong, dayNumber } from '#lib/time.ts';
  import Meteogram from './Meteogram.svelte';
  import Table48 from './Table48.svelte';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const VIEW = 'meteo.view48';
  const remembered = () => {
    try {
      return localStorage.getItem(VIEW) === 'table' ? 'table' : 'chart';
    } catch {
      return 'chart';
    }
  };
  let view = $state<'chart' | 'table'>(remembered());
  function show(next: 'chart' | 'table') {
    view = next;
    try {
      localStorage.setItem(VIEW, next);
    } catch {
      // Storage refused: the choice lasts until the page closes.
    }
  }

  const forecast = $derived(data.forecast.value);
  const hourly = $derived(forecast?.hourly);
  const times = $derived(hourly ? hourly.time.map(Date.parse) : []);
  const first = $derived(firstShown(times, data.clock));
  let picked = $state<number | null>(null);
  const selected = $derived(
    picked !== null && picked >= first && picked < times.length
      ? picked
      : nextHour(times, data.clock)
  );
  const issued = $derived(forecast ? Date.parse(forecast.issued_at) : 0);
  const sentence = $derived(
    hourly ? summary(hourly, data.clock, observed(data.now.value?.radar, data.clock)) : null
  );
  // The summary starts with the radar, so the block waits for now.json as well:
  // a sentence growing a moment later would move the page.
  const nowRead = $derived(data.now.value !== null || data.now.problem !== null);
  const lastFull = $derived(hourly ? (times[lastFullHour(hourly)] ?? 0) : 0);
  const hasGap = $derived(hourly?.temperature_c.mean.some((v) => v === null) ?? false);
  const hasDst = $derived(times.some((_, i) => dstLabel(times, i) !== null));

  // Everything the readout shows, as one sentence for the hour control.
  const readout = $derived.by(() => {
    if (!hourly) return null;
    const i = selected;
    const at = times[i] ?? 0;
    const label = dstLabel(times, i);
    const T = hourly.temperature_c;
    const n = hourly.rain.n_models[i] ?? 0;
    const m = hourly.rain.m_models[i] ?? 0;
    const amount = hourly.precipitation_mm.mean[i];
    return {
      when: `${weekdayLong(at)} ${dayNumber(at)}, ${hm(at)}${label ? ` (${label})` : ''}`,
      temp: T.mean[i] == null ? t('state.nodata') : temp(T.mean[i]),
      range:
        T.mean[i] == null ? '' : t('h48.readout_temp', { min: int(T.low[i]), max: int(T.high[i]) }),
      rain: models(n, m),
      mm: amount ? t('h48.readout_mm', { mm: mm(amount) }) : '',
      wind: wind(hourly.wind_kmh.mean[i], hourly.wind_dir_deg.mean[i]),
      gust: t('h48.cell_gust', { g: int(hourly.gust_kmh.mean[i]) }),
      cloud: t('h48.readout_cloud', { pct: pct(hourly.cloud_pct.mean[i]) })
    };
  });
  const spoken = $derived(
    readout
      ? [
          readout.when,
          `${readout.temp} ${readout.range}`,
          `${readout.rain} ${readout.mm}`,
          `${readout.wind} ${readout.gust}`,
          readout.cloud
        ]
          .map((part) => part.trim())
          .join(', ')
      : ''
  );

  // The browser's own Page Up and Page Down steps vary; the design wants six hours.
  function pageKeys(event: KeyboardEvent) {
    const step = event.key === 'PageUp' ? -6 : event.key === 'PageDown' ? 6 : 0;
    if (!step) return;
    event.preventDefault();
    picked = Math.min(times.length - 1, Math.max(first, selected + step));
  }
  const rangeMinMax = $derived.by(() => {
    if (!hourly) return null;
    const values = hourly.temperature_c.mean.filter(
      (v, i): v is number => v !== null && i >= first
    );
    return values.length
      ? { min: temp(Math.min(...values)), max: temp(Math.max(...values)) }
      : null;
  });
</script>

{#if !forecast || !hourly || !nowRead}
  {#if data.forecast.problem}
    <p class="note bad"><Icon name="bad" /><span>{t('state.forecast_missing')}</span></p>
  {:else}
    <div class="skel skel-48">{t('state.loading')}</div>
  {/if}
{:else}
  <p class="sec-meta">{t('h48.meta', { ora: hm(issued), stazione: data.town.station })}</p>
  {#if sentence}
    <p class="summary">
      {sentence.now ? `${sentence.now} ` : ''}<strong>{sentence.rain}</strong>
      {sentence.temp}
    </p>
  {/if}
  {#if hasDst}
    <p class="note info"><Icon name="info" /><span>{t('h48.dst_note')}</span></p>
  {/if}
  <div class="toolbar">
    <div class="seg" role="group" aria-label={t('h48.view_label')}>
      <button type="button" aria-pressed={view === 'chart'} onclick={() => show('chart')}
        >{t('h48.view_chart')}</button
      >
      <button type="button" aria-pressed={view === 'table'} onclick={() => show('table')}
        >{t('h48.view_table')}</button
      >
    </div>
  </div>
  {#if view === 'chart'}
    <div class="legend" aria-hidden="true">
      <span><i class="key line key-temp"></i>{t('h48.legend_mean')}</span>
      <span><i class="key band key-band"></i>{t('h48.legend_range')}</span>
      <span><i class="key bar key-rain"></i>{t('h48.legend_rain')}</span>
      <span><i class="key line key-wind"></i>{t('h48.legend_wind')}</span>
      <span><i class="key dot key-gust"></i>{t('h48.legend_gust')}</span>
    </div>
    {#if readout}
      <div class="readout" aria-label={t('h48.readout_label')}>
        <div class="when">{readout.when}</div>
        <div class="item">
          <span class="key line key-temp"></span><b>{readout.temp}</b>
          <span class="sub">{readout.range}</span>
        </div>
        <div class="item">
          <span class="key bar key-rain"></span><b>{readout.rain}</b>
          <span class="sub">{readout.mm}</span>
        </div>
        <div class="item">
          <span class="key line key-wind"></span><b>{readout.wind}</b>
          <span class="sub">{readout.gust}</span>
        </div>
        <div class="item"><span class="key band key-cloud"></span><span>{readout.cloud}</span></div>
      </div>
    {/if}
    <div
      role="img"
      aria-label={rangeMinMax
        ? t('h48.chart_aria', {
            min: rangeMinMax.min,
            max: rangeMinMax.max,
            pioggia: sentence?.rain ?? ''
          })
        : undefined}
    >
      <Meteogram
        {hourly}
        {first}
        now={data.clock}
        lat={data.town.lat}
        lon={data.town.lon}
        bind:selected={() => selected, (i) => (picked = i)}
      />
    </div>
    <input
      class="scrub"
      type="range"
      min={first}
      max={times.length - 1}
      step="1"
      value={selected}
      oninput={(event) => (picked = Number(event.currentTarget.value))}
      onkeydown={pageKeys}
      aria-label={t('h48.range_label')}
      aria-valuetext={spoken}
    />
    <p class="help">{t('h48.chart_help')}</p>
  {:else}
    <Table48 {hourly} {first} lat={data.town.lat} lon={data.town.lon} />
  {/if}
  <div class="foot">
    {#if hasGap}<p>{t('state.partial_hours')}</p>{/if}
    <p>{t('h48.footnote')}</p>
    <p>
      {t('h48.models_note', {
        m: hourly.temperature_c.m_models[0] ?? 0,
        ora1: `${dayName(lastFull, data.clock)} ${t('time.at', { ora: hm(lastFull) })}`
      })}
    </p>
  </div>
{/if}
