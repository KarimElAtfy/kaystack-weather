<script lang="ts">
  import { has, t } from '#lib/copy/t.ts';
  import {
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
  import { metarFreshness, radarAtTownFreshness } from '#lib/data/states.ts';
  import { classOf, className } from '#lib/radar/classes.ts';
  import { fromCover, fromMetar } from '#lib/symbols/pick.ts';
  import Sky from '#lib/symbols/Sky.svelte';
  import Icon from '#lib/symbols/Icon.svelte';
  import { skyName } from '#lib/symbols/words.ts';
  import { ago, hm, isNight } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const file = $derived(data.now.value);
  const metar = $derived(file?.metar ?? null);
  const radar = $derived(file?.radar ?? null);
  const rain = 0.2;

  const sky = $derived.by(() => {
    if (!metar) return null;
    const night = isNight(data.clock, data.town.lat, data.town.lon);
    return fromMetar(metar.weather) ?? fromCover(metar.cloud_cover, night);
  });
  const cover = (code: string | null | undefined) => {
    const key = `metar.cover.${code}`;
    return code && has(key) ? t(key) : null;
  };
</script>

{#if !file && !data.now.problem}
  <div class="skel skel-now">{t('state.loading')}</div>
{:else}
  <div class="now-grid">
    <div>
      {#if !metar}
        <p class="note bad"><Icon name="bad" /><span>{t('state.metar_missing')}</span></p>
      {:else}
        {@const at = Date.parse(metar.observed_at)}
        {@const freshness = metarFreshness(metar, data.clock)}
        {@const source = t('now.source_metar', {
          aeroporto: metar.name,
          km: km(metar.distance_km),
          ora: hm(at),
          fa: ago(at, data.clock)
        })}
        {#if freshness === 'expired'}
          <p class="note">
            <Icon name="warn" /><span>{t('state.metar_expired', { ora: hm(at) })}</span>
          </p>
          <p class="src">{source}</p>
        {:else}
          {@const stale = freshness === 'stale'}
          {@const dir = point(metar.wind_dir_deg)}
          {@const rh = humidity(metar.temperature_c, metar.dew_point_c)}
          {#if stale}
            <p class="note">
              <Icon name="warn" /><span
                >{t('state.metar_stale', { ora: hm(at), fa: ago(at, data.clock) })}</span
              >
            </p>
          {/if}
          <div class="now-hero" class:stale-val={stale}>
            {#if sky}<Sky {sky} size={56} label={skyName(sky)} />{/if}
            <p class="now-temp">
              <span class="vh">{t('now.temp_label')}: </span>{metar.temperature_c === null
                ? t('state.nodata')
                : int(metar.temperature_c)}<span class="u">{t('unit.c')}</span>
            </p>
            <p class="now-wx">
              {weather(metar.weather) ?? cover(metar.cloud_cover) ?? t('now.weather_none')}
              {#if stale}<span class="tag">{t('state.stale_tag')}</span>{/if}
            </p>
          </div>
          <p class="src">{source}</p>
          <dl class="facts" class:stale-val={stale}>
            <div>
              <dt>{t('now.wind')}</dt>
              <dd>
                {#if metar.wind_kmh === null}<abbr title={t('state.nodata_title')}
                    >{t('state.nodata')}</abbr
                  >{:else if metar.wind_kmh < 2}{t('wind.calm')}{:else}<span class="nw"
                    >{kmh(metar.wind_kmh)}</span
                  ><span class="sub"
                    >{dir ? t('wind.from', { dir: directionLong(dir) }) : t('wind.variable')}</span
                  >{/if}
              </dd>
            </div>
            <div>
              <dt>{t('now.gust')}</dt>
              <dd>
                {#if metar.gust_kmh !== null}<span class="nw">{kmh(metar.gust_kmh)}</span
                  >{:else if metar.raw && !/G\d\d/.test(metar.raw)}{t('now.no_gust')}{:else}<abbr
                    title={t('state.nodata_title')}>{t('state.nodata')}</abbr
                  >{/if}
              </dd>
            </div>
            <div>
              <dt>{t('now.humidity')}</dt>
              <dd title={t('now.humidity_note')}>
                {#if rh === null}<abbr title={t('state.nodata_title')}>{t('state.nodata')}</abbr
                  >{:else}{pct(rh)}<span class="sub">{t('now.humidity_short')}</span>{/if}
              </dd>
            </div>
            <div>
              <dt>{t('now.dewpoint')}</dt>
              <dd>
                {#if metar.dew_point_c === null}<abbr title={t('state.nodata_title')}
                    >{t('state.nodata')}</abbr
                  >{:else}<span class="nw">{temp(metar.dew_point_c)}</span>{/if}
              </dd>
            </div>
            <div>
              <dt>{t('now.visibility')}</dt>
              <dd>
                {#if metar.visibility_m === null}<abbr title={t('state.nodata_title')}
                    >{t('state.nodata')}</abbr
                  >{:else}<span class="nw">{visibility(metar.visibility_m)}</span>{/if}
              </dd>
            </div>
            {#if metar.weather}
              <!-- Without weather the hero line already names the cloud cover. -->
              <div>
                <dt>{t('now.sky')}</dt>
                <dd>
                  {#if cover(metar.cloud_cover)}{cover(metar.cloud_cover)}{:else}<abbr
                      title={t('state.nodata_title')}>{t('state.nodata')}</abbr
                    >{/if}
                </dd>
              </div>
            {/if}
          </dl>
          {#if metar.raw}
            <details class="raw">
              <summary>{t('now.metar_raw')}</summary>
              <code>{metar.raw}</code>
            </details>
          {/if}
        {/if}
      {/if}
    </div>

    <div class="rainnow">
      <h3>{t('now.rain_h3')}</h3>
      {#if !radar || radarAtTownFreshness(radar, data.clock) === 'expired'}
        <p class="answer muted">{t('state.radar_missing')}</p>
      {:else}
        {@const at = Date.parse(radar.frame_time)}
        {@const stale = radarAtTownFreshness(radar, data.clock) === 'stale'}
        {@const here = radar.rate_mm_h}
        {@const near10 = radar.max_10km_mm_h ?? 0}
        <p class="answer" class:stale-val={stale}>
          {#if radar.no_data || here === null}
            {t('state.radar_nodata_here')}
          {:else if here >= rain}
            {t(stale ? 'now.rain_here_past' : 'now.rain_here', {
              intensita: className(classOf(here)),
              valore: mmh(here),
              ora: hm(at)
            })}
          {:else if stale}
            {t('now.rain_none_past', { ora: hm(at) })}
          {:else}
            {near10 >= rain ? t('now.rain_none_near') : t('now.rain_none')}
          {/if}
          {#if stale}<span class="tag">{t('state.stale_tag')}</span>{/if}
        </p>
        {#if (here ?? 0) >= rain || near10 >= rain}
          <ul>
            <li>
              {(radar.max_5km_mm_h ?? 0) >= rain
                ? t('now.rain_5', { valore: mmh(radar.max_5km_mm_h) })
                : t('now.rain_5_none')}
            </li>
            <li>
              {near10 >= rain ? t('now.rain_10', { valore: mmh(near10) }) : t('now.rain_10_none')}
            </li>
          </ul>
        {/if}
        <p class="src">{t('now.source_radar', { ora: hm(at), fa: ago(at, data.clock) })}</p>
      {/if}
      <p class="links"><a href="#radar">{t('now.to_radar')}</a></p>
    </div>
  </div>
{/if}
