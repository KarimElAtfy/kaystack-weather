<script lang="ts">
  // The last hour of radar: the map under and over a canvas that paints the
  // sprite's classes in this theme's colours, so heavier rain stands out more
  // against the map in light and dark alike. It never plays by itself.
  import { onMount } from 'svelte';
  import { has, t } from '#lib/copy/t.ts';
  import { radarMapFreshness } from '#lib/data/states.ts';
  import { className, range, type Bin } from '#lib/radar/classes.ts';
  import { aroundTown, paint, rgba, type Rgba } from '#lib/radar/sprite.ts';
  import Icon from '#lib/symbols/Icon.svelte';
  import { ago, hm } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const radar = $derived(data.radar.value);
  const frames = $derived(
    radar && data.frames?.sprite === radar.sprite ? data.frames.frames : null
  );
  const last = $derived(radar ? radar.frames.length - 1 : 0);
  let chosen = $state<number | null>(null);
  const shown = $derived(chosen ?? last);
  const frame = $derived(radar?.frames[shown]);
  // Until the sprite is decoded nothing is painted, and a clean map would read as dry.
  const loading = $derived(!!radar && !frames && !data.spriteFailed);
  const lastTime = $derived(radar?.frames.at(-1)?.time ?? null);
  const freshness = $derived(
    lastTime
      ? radarMapFreshness(lastTime, data.now.value?.radar?.stale_after_min ?? 15, data.clock)
      : 'expired'
  );
  const townName = (slug: string) => {
    const key = `town.${slug}`;
    return has(key) ? t(key) : slug;
  };
  const town = $derived(townName(data.town.slug));

  const classText = (index: number, scale: Bin[]) => {
    const bin = scale.find((b) => b.index === index);
    return bin ? `${className(index)}, ${range(bin)} ${t('unit.mmh')}` : className(index);
  };

  // Said in words for every frame, from the same cells the canvas paints.
  const sentence = $derived.by(() => {
    if (!radar || !frame) return '';
    if (frame.missing) return `${hm(Date.parse(frame.time))}, ${t('radar.frame_missing')}`;
    const cells = frames?.[shown];
    if (!cells) return '';
    const { here, near } = aroundTown(cells, radar.frame_width_px, radar.town_px, radar.km_per_px);
    const qui =
      here < 0
        ? t('state.radar_nodata_here')
        : here === 0
          ? t('radar.sum_here_none')
          : t('radar.sum_here', { classe: classText(here, radar.scale) });
    const vicino =
      near === 0
        ? t('radar.sum_near_none')
        : t('radar.sum_near', { classe: classText(near, radar.scale) });
    return t('radar.summary', { ora: hm(Date.parse(frame.time)), qui, vicino });
  });

  // The theme's colours by class index: 1 to 6 rain, 7 and 8 the no-data hatch.
  let palette = $state<Rgba[]>([]);
  function readPalette() {
    const style = getComputedStyle(document.documentElement);
    const colour = (name: string) => rgba(style.getPropertyValue(name));
    const line = colour('--nodata');
    palette = [
      [0, 0, 0, 0],
      ...[1, 2, 3, 4, 5, 6].map((i) => colour(`--r${i}`)),
      line,
      [line[0], line[1], line[2], Math.round(line[3] * 0.28)]
    ];
  }

  let canvas = $state<HTMLCanvasElement>();
  $effect(() => {
    const cells = frames?.[shown];
    const context = canvas?.getContext('2d');
    if (!radar || !context || !palette.length) return;
    const image = context.createImageData(radar.frame_width_px, radar.frame_height_px);
    if (cells && !frame?.missing) paint(cells, palette, image.data);
    context.putImageData(image, 0, 0);
  });

  let playing = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  function stop() {
    clearTimeout(timer);
    playing = false;
  }
  function step() {
    const next = shown >= last ? 0 : shown + 1;
    chosen = next;
    timer = setTimeout(step, next === last ? 1400 : 450);
  }
  function toggle() {
    if (playing) return stop();
    playing = true;
    step();
  }

  let root = $state<HTMLElement>();
  onMount(() => {
    readPalette();
    const scheme = matchMedia('(prefers-color-scheme: dark)');
    scheme.addEventListener('change', readPalette);
    const hidden = () => document.visibilityState === 'hidden' && stop();
    document.addEventListener('visibilitychange', hidden);
    const seen = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          data.seeRadar();
          seen.disconnect();
        }
      },
      { rootMargin: '300px' }
    );
    if (root) seen.observe(root);
    return () => {
      stop();
      seen.disconnect();
      scheme.removeEventListener('change', readPalette);
      document.removeEventListener('visibilitychange', hidden);
    };
  });

  const unavailable = $derived(
    (!radar && data.radar.problem !== null) || freshness === 'expired' || data.spriteFailed
  );
  $effect(() => {
    if (unavailable) data.askStatus();
  });
  const since = $derived(lastTime ?? data.status.value?.sources.radar?.data_time ?? null);
  const rings = [10, 25, 50];
</script>

{#snippet credit(map: boolean)}
  <p class="credit">
    <strong>{t('radar.credit')}</strong>{#if map}. {t('radar.basemap_credit')}{/if}
  </p>
{/snippet}

<div bind:this={root}>
  {#if !radar && !data.radar.problem}
    <div class="skel skel-radar">{t('state.loading')}</div>
    <!-- The full credit from the start: only "Radar non disponibile" has no map. -->
    {@render credit(true)}
  {:else if unavailable || !radar}
    <div class="map-empty">
      <div>
        <p class="title">{t('radar.unavailable')}</p>
        {#if since}
          <p class="small muted">
            {t('radar.unavailable_since', {
              ora: hm(Date.parse(since)),
              fa: ago(Date.parse(since), data.clock)
            })}
          </p>
        {/if}
      </div>
    </div>
    {@render credit(false)}
  {:else}
    {@const width = radar.frame_width_px}
    {@const height = radar.frame_height_px}
    {@const tx = radar.town_px.x + 0.5}
    {@const ty = radar.town_px.y + 0.5}
    {@const map = `/radar/${data.town.slug}.svg`}
    {#if freshness === 'stale' && lastTime}
      <p class="note">
        <Icon name="warn" /><span>
          {t('radar.stale', {
            ora: hm(Date.parse(lastTime)),
            fa: ago(Date.parse(lastTime), data.clock)
          })}
        </span>
      </p>
    {/if}
    <div
      class="map"
      role="img"
      aria-label={t('radar.map_label', {
        paese: town,
        ora: frame ? hm(Date.parse(frame.time)) : '',
        sintesi: sentence
      })}
    >
      <svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true"
        ><use href="{map}#under" /></svg
      >
      <canvas bind:this={canvas} {width} {height}></canvas>
      {#if loading || frame?.missing}<div class="veil" aria-hidden="true"></div>{/if}
      <svg viewBox="0 0 {width} {height}" aria-hidden="true">
        <use href="{map}#over" />
        {#each rings as km (km)}
          {@const r = km / radar.km_per_px}
          <circle class="ring" cx={tx} cy={ty} {r} />
          {#if ty - r > 4}
            <text class="label" x={tx} y={ty - r - 0.8} text-anchor="middle" font-size="3.2"
              >{km} {t('unit.km')}</text
            >
          {/if}
        {/each}
        <circle class="town-halo" cx={tx} cy={ty} r="2.2" />
        <circle class="town-ring" cx={tx} cy={ty} r="2.2" />
        <circle class="town-dot" cx={tx} cy={ty} r="0.7" />
        <text class="label" x={tx + 3.2} y={ty + 4.6} font-size="4" font-weight="700">{town}</text>
        <g transform="translate({width - 16} {height - 5})">
          <rect
            class="bar-back"
            x="-1.5"
            y="-4.6"
            width={10 / radar.km_per_px + 4}
            height="6.6"
            rx="1"
          />
          <line class="bar" x1="0" x2={10 / radar.km_per_px} y1="0" y2="0" />
          <line class="bar" x1="0" x2="0" y1="-1" y2="0.6" />
          <line class="bar" x1={10 / radar.km_per_px} x2={10 / radar.km_per_px} y1="-1" y2="0.6" />
          <text class="label" x={5 / radar.km_per_px} y="-1.4" text-anchor="middle" font-size="2.8"
            >10 {t('unit.km')}</text
          >
        </g>
      </svg>
      {#if frame && !loading}
        <div class="stamp">{hm(Date.parse(frame.time))}<span>{t('radar.observed')}</span></div>
      {/if}
      {#if loading}
        <div class="veil-box"><p>{t('radar.loading')}</p></div>
      {:else if frame?.missing}
        <div class="veil-box">
          <p>{t('radar.frame_missing_box', { ora: hm(Date.parse(frame.time)) })}</p>
        </div>
      {/if}
    </div>
    <div class="controls">
      <button class="btn play" type="button" disabled={loading} onclick={toggle}>
        <Icon name={playing ? 'pause' : 'play'} />{playing ? t('radar.pause') : t('radar.play')}
      </button>
      <input
        type="range"
        min="0"
        max={last}
        step="1"
        value={shown}
        disabled={loading}
        oninput={(event) => {
          stop();
          chosen = Number(event.currentTarget.value);
        }}
        aria-label={t('radar.slider')}
        aria-valuetext={loading
          ? t('radar.loading')
          : frame
            ? sentence || hm(Date.parse(frame.time))
            : undefined}
      />
      <span class="ftime" aria-hidden="true"
        >{frame && !loading ? hm(Date.parse(frame.time)) : ''}</span
      >
      <button
        class="btn latest"
        type="button"
        disabled={loading || (shown === last && !playing)}
        onclick={() => {
          stop();
          chosen = null;
        }}>{t('radar.latest')}</button
      >
    </div>
    <p class="rsum">{sentence}</p>
    <div class="rlegend">
      <h3>{t('radar.legend_title')}</h3>
      <ul>
        {#each radar.scale as bin (bin.index)}
          <li>
            <span class="sw sw-{bin.index}"></span><b>{range(bin)}</b><span
              >{className(bin.index)}</span
            >
          </li>
        {/each}
        <li class="nd">
          <span class="sw sw-nodata"></span><span>{t('radar.legend_nodata')}</span>
        </li>
      </ul>
      <p class="credit">{t('radar.rings')}</p>
    </div>
    {@render credit(true)}
  {/if}
</div>
