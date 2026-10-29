<script lang="ts">
  import { t } from '#lib/copy/t.ts';
  import { int, mm, models, temp, wind } from '#lib/format.ts';
  import { firstShown, observed, summary } from '#lib/chart/h48.ts';
  import Icon from '#lib/symbols/Icon.svelte';
  import { dayNumber, dstLabel, hm, weekdayLong } from '#lib/time.ts';
  import Meteogram from './Meteogram.svelte';
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
  // The table holds every number of the chart; it loads only when asked for.
  const table = $derived(view === 'table' ? import('./Table48.svelte') : null);

  const forecast = $derived(data.forecast.value);
  const hourly = $derived(forecast?.hourly);
  const times = $derived(hourly ? hourly.time.map(Date.parse) : []);
  const first = $derived(firstShown(times, data.clock));
  // No hour is chosen until someone touches the chart or moves the range.
  let picked = $state<number | null>(null);
  const selected = $derived(
    picked !== null && picked >= first && picked < times.length ? picked : null
  );
  const hasGap = $derived(hourly?.temperature_c.mean.some((v) => v === null) ?? false);
  // Without the correction the page says so, and never calls the values corrected.
  const raw = $derived(hourly ? !hourly.temperature_c.corrected : false);
  const hasDst = $derived(times.some((_, i) => dstLabel(times, i) !== null));

  const readout = $derived.by(() => {
    if (!hourly || selected === null) return null;
    const i = selected;
    const label = dstLabel(times, i);
    const T = hourly.temperature_c;
    const amount = hourly.precipitation_mm.mean[i];
    return [
      `${weekdayLong(times[i]!)} ${dayNumber(times[i]!)}, ${hm(times[i]!)}${label ? ` (${label})` : ''}`,
      T.mean[i] == null
        ? t('state.nodata')
        : `${temp(T.mean[i])}, ${t('h48.readout_temp', { min: int(T.low[i]), max: int(T.high[i]) })}`,
      `${t('h48.col_rain')}: ${models(hourly.rain.n_models[i] ?? 0, hourly.rain.m_models[i] ?? 0)}${amount ? `, ${t('h48.readout_mm', { mm: mm(amount) })}` : ''}`,
      `${wind(hourly.wind_kmh.mean[i], hourly.wind_dir_deg.mean[i])}, ${t('h48.cell_gust', { g: int(hourly.gust_kmh.mean[i]) })}`
    ];
  });
  const spoken = $derived(readout?.join(', ') ?? '');

  // The browser's own Page Up and Page Down steps vary; the design wants six hours.
  function pageKeys(event: KeyboardEvent) {
    const step = event.key === 'PageUp' ? -6 : event.key === 'PageDown' ? 6 : 0;
    if (!step) return;
    event.preventDefault();
    picked = Math.min(times.length - 1, Math.max(first, (selected ?? first) + step));
  }
  const rain = $derived(
    hourly ? summary(hourly, data.clock, observed(data.now.value?.radar, data.clock)).rain : ''
  );
  const range = $derived.by(() => {
    const values = (hourly?.temperature_c.mean ?? []).filter(
      (v, i): v is number => v !== null && i >= first
    );
    return values.length
      ? { min: temp(Math.min(...values)), max: temp(Math.max(...values)) }
      : null;
  });
</script>

{#if !forecast || !hourly}
  {#if data.forecast.problem}
    <p class="note bad"><Icon name="bad" /><span>{t('state.forecast_missing')}</span></p>
  {:else}
    <div class="skel skel-48">{t('state.loading')}</div>
  {/if}
{:else}
  {#if raw}
    <p class="note info"><Icon name="info" /><span>{t('h48.note_raw')}</span></p>
  {/if}
  {#if hasDst}
    <p class="note info"><Icon name="info" /><span>{t('h48.dst_note')}</span></p>
  {/if}
  <div class="seg" role="group" aria-label={t('h48.view_label')}>
    <button type="button" aria-pressed={view === 'chart'} onclick={() => show('chart')}
      >{t('h48.view_chart')}</button
    >
    <button type="button" aria-pressed={view === 'table'} onclick={() => show('table')}
      >{t('h48.view_table')}</button
    >
  </div>
  {#if view === 'chart'}
    <div
      role="img"
      aria-label={range
        ? t('h48.chart_aria', { min: range.min, max: range.max, pioggia: rain })
        : undefined}
    >
      <Meteogram
        {hourly}
        {first}
        {readout}
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
      value={selected ?? first}
      oninput={(event) => (picked = Number(event.currentTarget.value))}
      onkeydown={pageKeys}
      aria-label={t('h48.range_label')}
      aria-valuetext={spoken || undefined}
    />
  {:else if table}
    {#await table then { default: Table48 }}
      <Table48 {hourly} {first} lat={data.town.lat} lon={data.town.lon} />
    {/await}
  {/if}
  <div class="foot">
    {#if hasGap && !raw}<p>{t('state.partial_hours')}</p>{/if}
    <p>{t(raw ? 'h48.footnote_raw' : 'h48.footnote')}</p>
  </div>
{/if}

<style>
  @layer blocks {
    .seg {
      display: inline-flex;
      margin-block-end: var(--space-3);
    }
    .seg button {
      min-block-size: var(--tap);
      padding-inline: var(--space-4);
      font: inherit;
      font-size: var(--text-m);
      color: var(--ink-2);
      background: var(--paper);
      border: 1px solid var(--ink-3);
      border-radius: 0;
    }
    .seg button + button {
      border-inline-start: 0;
    }
    .seg button[aria-pressed='true'] {
      color: var(--paper);
      background: var(--ink);
      border-color: var(--ink);
    }
    .scrub {
      display: block;
      inline-size: 100%;
      min-block-size: var(--tap);
      margin: var(--space-2) 0 0;
      accent-color: var(--ink);
    }
    .foot {
      margin-block-start: var(--space-3);
      font-size: var(--text-s);
      color: var(--ink-2);
    }
    .foot p {
      margin: 0;
    }
  }
</style>
