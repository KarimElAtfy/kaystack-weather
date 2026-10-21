<script lang="ts">
  // Ten days as a table: minimum to maximum on one scale shared by every row,
  // the range between models as lighter ends, rain as models out of models.
  import { t } from '#lib/copy/t.ts';
  import { daysShown } from '#lib/chart/d10.ts';
  import { deg, int, models } from '#lib/format.ts';
  import { pick } from '#lib/symbols/pick.ts';
  import Sky from '#lib/symbols/Sky.svelte';
  import Icon from '#lib/symbols/Icon.svelte';
  import { skyAlt } from '#lib/symbols/words.ts';
  import { dayMonth, dayNumber, localDate, weekdayShort, ymd } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const forecast = $derived(data.forecast.value);
  const daily = $derived(forecast?.daily);
  const DAY = 86_400_000;
  const STOPS = [-10, 0, 10, 20, 30, 40];

  const scale = $derived.by(() => {
    const all = [...(daily?.tmin_c.low ?? []), ...(daily?.tmax_c.high ?? [])].filter(
      (v): v is number => v !== null
    );
    const low = Math.floor(Math.min(...all, 0));
    const high = Math.ceil(Math.max(...all, 1));
    return { low, high, at: (v: number) => ((v - low) / (high - low)) * 100 };
  });

  const rows = $derived.by(() => {
    if (!forecast || !daily) return [];
    const issueDay = localDate(ymd(Date.parse(forecast.issued_at)));
    return daysShown(daily).map((k) => {
      const day = daily.day[k] ?? '';
      const at = localDate(day);
      const ahead = Math.round((at - issueDay) / DAY);
      const previous = k > 0 ? localDate(daily.day[k - 1] ?? day) : at;
      const n = daily.rain.n_models[k] ?? 0;
      const m = daily.rain.m_models[k] ?? 0;
      // No cloud cover, no sky: a symbol would be a forecast nobody made.
      const cloud = daily.cloud_pct?.mean[k];
      const sky =
        cloud == null ? null : pick(cloud, n, m, daily.precipitation_mm?.mean[k], false, true);
      const weekday = weekdayShort(at);
      return {
        day,
        name:
          ahead === 1
            ? t('d10.tomorrow')
            : `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)} ${dayNumber(at)}`,
        sub:
          ahead === 1
            ? `${weekday} ${dayNumber(at)}`
            : Number(dayNumber(at)) < Number(dayNumber(previous))
              ? dayMonth(at).split(' ').pop()
              : '',
        // Less reliable: the correction comes from a shorter lead than the day's own.
        far: (daily.tmax_c.lead_band[k] ?? 0) < ahead,
        n,
        m,
        sky,
        min: { mean: daily.tmin_c.mean[k], low: daily.tmin_c.low[k], high: daily.tmin_c.high[k] },
        max: { mean: daily.tmax_c.mean[k], low: daily.tmax_c.low[k], high: daily.tmax_c.high[k] }
      };
    });
  });
  const near = $derived(rows.filter((row) => !row.far));
  const far = $derived(rows.filter((row) => row.far));
  const width = (a: number, b: number, least: number) => Math.max(least, scale.at(b) - scale.at(a));
</script>

{#snippet row(r: (typeof rows)[number])}
  {@const both = r.min.mean != null && r.max.mean != null}
  <tr class:far={r.far}>
    <th scope="row" class="c-day"
      >{r.name}{#if r.sub}<span class="d">{r.sub}</span>{/if}</th
    >
    <td class="c-sky">
      {#if r.sky}
        <Sky sky={r.sky} size={28} label={skyAlt(r.sky, r.n, r.m)} />
      {:else}
        <span class="vh">{t('state.nodata_title')}</span>
      {/if}
    </td>
    <td class="c-t min">{r.min.mean == null ? t('state.nodata') : deg(r.min.mean)}</td>
    <td class="c-bar">
      <svg
        class="dbar"
        viewBox="0 0 100 22"
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <rect class="track" x="0" y="10" width="100" height="2" />
        {#if r.min.low != null && r.min.high != null}
          <rect
            class="ends"
            x={scale.at(r.min.low)}
            y="9"
            width={width(r.min.low, r.min.high, 1)}
            height="4"
            fill="url(#t-scale)"
          />
        {/if}
        {#if r.max.low != null && r.max.high != null}
          <rect
            class="ends"
            x={scale.at(r.max.low)}
            y="9"
            width={width(r.max.low, r.max.high, 1)}
            height="4"
            fill="url(#t-scale)"
          />
        {/if}
        {#if both}
          <rect
            x={scale.at(r.min.mean ?? 0)}
            y="7"
            width={width(r.min.mean ?? 0, r.max.mean ?? 0, 2)}
            height="8"
            fill="url(#t-scale)"
          />
          {#if r.far}
            <rect
              x={scale.at(r.min.mean ?? 0)}
              y="7"
              width={width(r.min.mean ?? 0, r.max.mean ?? 0, 2)}
              height="8"
              fill="url(#t-far)"
            />
          {/if}
        {/if}
      </svg>
      <span class="vh">
        {both
          ? t('d10.cell_range', {
              min: int(r.min.mean),
              minlo: int(r.min.low),
              minhi: int(r.min.high),
              max: int(r.max.mean),
              maxlo: int(r.max.low),
              maxhi: int(r.max.high)
            })
          : t('state.nodata_title')}
      </span>
    </td>
    <td class="c-t">{r.max.mean == null ? t('state.nodata') : deg(r.max.mean)}</td>
    <td class="c-rain">
      <span class="rainc" class:zero={!r.n}>
        <span aria-hidden="true">{t('models.short', { n: r.n, m: r.m })}</span>
        <span class="vh">{models(r.n, r.m)}</span>
        <svg class="meter" viewBox="0 0 36 4" aria-hidden="true" focusable="false">
          <rect class="track" width="36" height="4" rx="2" />
          <rect class="fill" width={r.m ? (r.n / r.m) * 36 : 0} height="4" rx="2" />
        </svg>
      </span>
    </td>
  </tr>
{/snippet}

{#if !forecast || !daily}
  {#if data.forecast.problem}
    <p class="note bad"><Icon name="bad" /><span>{t('state.forecast_missing')}</span></p>
  {:else}
    <div class="skel skel-10">{t('state.loading')}</div>
  {/if}
{:else}
  <!-- One gradient for every bar: the colour follows the temperature, not the row. -->
  <svg width="0" height="0" aria-hidden="true" focusable="false" class="vh">
    <defs>
      <linearGradient
        id="t-scale"
        gradientUnits="userSpaceOnUse"
        x1={scale.at(-10)}
        x2={scale.at(40)}
        y1="0"
        y2="0"
      >
        {#each STOPS as stop, i (stop)}
          <stop offset={i / (STOPS.length - 1)} class="ts-{stop < 0 ? 'm10' : stop}" />
        {/each}
      </linearGradient>
      <pattern
        id="t-far"
        width="5"
        height="5"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <line class="far-hatch" x1="0" y1="0" x2="0" y2="5" />
      </pattern>
    </defs>
  </svg>
  <table class="days">
    <caption class="vh">{t('d10.caption')}</caption>
    <thead>
      <tr>
        <th scope="col" class="c-day">{t('d10.col_day')}</th>
        <th scope="col" class="c-sky"><span class="vh">{t('d10.col_sky')}</span></th>
        <th scope="col" class="c-t"
          ><abbr title={t('d10.col_min')}>{t('d10.col_min_short')}</abbr></th
        >
        <th scope="col" class="c-bar"><span class="vh">{t('h48.legend_range')}</span></th>
        <th scope="col" class="c-t"
          ><abbr title={t('d10.col_max')}>{t('d10.col_max_short')}</abbr></th
        >
        <th scope="col" class="c-rain">{t('d10.col_rain')}</th>
      </tr>
    </thead>
    <tbody>
      {#each near as r (r.day)}{@render row(r)}{/each}
    </tbody>
    {#if far.length}
      <tbody>
        <tr class="sep">
          <th colspan="6" scope="rowgroup">
            <span class="t"><Icon name="warn" />{t('d10.less_reliable_h3')}</span>
            <span class="n">{t('d10.less_reliable_note', { m: far[0]?.m ?? 0 })}</span>
          </th>
        </tr>
        {#each far as r (r.day)}{@render row(r)}{/each}
      </tbody>
    {/if}
  </table>
  <div class="foot">
    <p>{t('d10.legend_bar')}</p>
    <p>{t('d10.footnote', { stazione: data.town.station })}</p>
  </div>
{/if}
