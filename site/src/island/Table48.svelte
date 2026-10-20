<script lang="ts">
  // The 48 hours as a table: every number of the chart, one row per hour, one
  // group per local day. It is the chart's full equivalent, not a summary.
  import { t } from '#lib/copy/t.ts';
  import { directionShort, int, mm, models, pct, point } from '#lib/format.ts';
  import { pick } from '#lib/symbols/pick.ts';
  import Sky from '#lib/symbols/Sky.svelte';
  import { skyAlt } from '#lib/symbols/words.ts';
  import { dayMonth, dstLabel, hm, isNight, repeatedHour, weekdayLong, ymd } from '#lib/time.ts';
  import type { ForecastFile } from '#lib/data/decode.ts';

  type Props = { hourly: ForecastFile['hourly']; first: number; lat: number; lon: number };
  let { hourly, first, lat, lon }: Props = $props();

  const times = $derived(hourly.time.map(Date.parse));
  const days = $derived.by(() => {
    const groups: { day: string; at: number; hours: number[]; dst: boolean }[] = [];
    for (let i = first; i < times.length; i++) {
      const at = times[i] ?? 0;
      const day = ymd(at);
      if (groups.at(-1)?.day !== day) groups.push({ day, at, hours: [], dst: false });
      const group = groups.at(-1)!;
      group.hours.push(i);
      if (repeatedHour(times, i)) group.dst = true;
    }
    return groups;
  });
</script>

<table class="data">
  <caption class="vh">{t('h48.table_caption')}</caption>
  <colgroup
    ><col class="c-time" /><col class="c-sky" /><col class="c-temp" /><col class="c-rain" /><col
      class="c-wind"
    /></colgroup
  >
  <thead>
    <tr>
      <th scope="col">{t('h48.col_time')}</th>
      <th scope="col">{t('h48.col_sky')}<span class="sub">{t('h48.col_cloud')}</span></th>
      <th scope="col">{t('h48.col_temp')}<span class="sub">{t('h48.col_temp_sub')}</span></th>
      <th scope="col">{t('h48.col_rain')}<span class="sub">{t('h48.col_rain_sub')}</span></th>
      <th scope="col">{t('h48.col_wind')}<span class="sub">{t('h48.col_wind_sub')}</span></th>
    </tr>
  </thead>
  {#each days as group (group.day)}
    <tbody>
      <tr class="dayrow">
        <th colspan="5" scope="colgroup">
          {weekdayLong(group.at)}
          {dayMonth(group.at)}
          {#if group.dst}<span class="dst">{t('h48.dst_note')}</span>{/if}
        </th>
      </tr>
      {#each group.hours as i (i)}
        {@const at = times[i] ?? 0}
        {@const n = hourly.rain.n_models[i] ?? 0}
        {@const m = hourly.rain.m_models[i] ?? 0}
        {@const sky = pick(
          hourly.cloud_pct.mean[i],
          n,
          m,
          hourly.precipitation_mm.mean[i],
          isNight(at, lat, lon),
          false
        )}
        {@const speed = hourly.wind_kmh.mean[i]}
        {@const dir = point(hourly.wind_dir_deg.mean[i])}
        {@const label = dstLabel(times, i)}
        <tr class:night={isNight(at, lat, lon)}>
          <th scope="row">
            <span class="vh">{t('time.hour_word', { ora: '' })}</span>{hm(at)}
            {#if label}<span class="sub">{label}</span>{/if}
          </th>
          <td>
            <span class="sky">
              <Sky {sky} size={24} label={skyAlt(sky, n, m)} />
              <span class="xsmall muted">{pct(hourly.cloud_pct.mean[i])}</span>
            </span>
          </td>
          {#if hourly.temperature_c.mean[i] == null}
            <td><abbr title={t('state.nodata_title')}>{t('state.nodata')}</abbr></td>
          {:else}
            <td>
              <b class="nw">{int(hourly.temperature_c.mean[i])} {t('unit.c')}</b>
              <span class="sub">
                {t('h48.cell_range', {
                  min: int(hourly.temperature_c.low[i]),
                  max: int(hourly.temperature_c.high[i])
                })}
              </span>
            </td>
          {/if}
          <td>
            <b aria-hidden="true">{t('models.short', { n, m })}</b><span class="vh"
              >{models(n, m)}</span
            >
            {#if hourly.precipitation_mm.mean[i]}<span class="sub"
                >{mm(hourly.precipitation_mm.mean[i])}</span
              >{/if}
          </td>
          <td>
            <span class="nw">
              {#if speed != null && speed >= 2 && dir}
                <svg class="warr" width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">
                  <path
                    fill="currentColor"
                    transform="rotate({((hourly.wind_dir_deg.mean[i] ?? 0) + 180) % 360})"
                    d="M0 -5.5 L3.4 3 L0 1.1 L-3.4 3 Z"
                  />
                </svg>
              {/if}
              <b>{speed == null ? t('state.nodata') : speed < 2 ? t('wind.calm') : int(speed)}</b>
              {#if speed != null && speed >= 2}{dir ? directionShort(dir) : t('wind.variable')}{/if}
            </span>
            <span class="sub">{t('h48.cell_gust', { g: int(hourly.gust_kmh.mean[i]) })}</span>
          </td>
        </tr>
      {/each}
    </tbody>
  {/each}
</table>
