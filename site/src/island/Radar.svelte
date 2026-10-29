<script lang="ts">
  // The last hour of radar: the map under and over a canvas that paints the
  // sprite's classes in this theme's colours, so heavier rain stands out more
  // against the map in light and dark alike. The names on the map are page
  // text. It never plays by itself.
  import { onMount } from 'svelte';
  import { has, t } from '#lib/copy/t.ts';
  import { radarMapFreshness } from '#lib/data/states.ts';
  import { bound, className, range, type Bin } from '#lib/radar/classes.ts';
  import { place, type Box, type Name, type Spot } from '#lib/radar/labels.ts';
  import { aroundTown, paint, rgba, type Rgba } from '#lib/radar/sprite.ts';
  import cities from '#lib/radar/maps/cities.json';
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
      ...[1, 2, 3, 4, 5, 6].map((i) => colour(`--radar-${i}`)),
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
  // While the images load the controls stay in the tab order with
  // aria-disabled and ignore activation: disabled would take them out of it,
  // and on a phone they load only once in view.
  function toggle() {
    if (loading) return;
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
  const RINGS = [10, 25, 50];

  // The names on the map. Each is measured where it is drawn, then placed by
  // the rule in labels.ts; the ones left out are hidden, never shrunk.
  const points = $derived(
    (cities as Record<string, { name: string; x: number; y: number }[]>)[data.town.slug] ?? []
  );
  let mapSize = $state(0);
  let stamp = $state<HTMLElement>();
  let names = $state<Record<string, HTMLElement>>({});
  let spots = $state(new Map<string, Spot>());
  // The town's name width changes with the text size, and calls for placing again.
  let townWidth = $state(0);
  $effect(() => {
    if (!radar || !mapSize || !townWidth) return;
    const k = mapSize / radar.frame_width_px;
    const tx = (radar.town_px.x + 0.5) * k;
    const ty = (radar.town_px.y + 0.5) * k;
    const size = (key: string) => {
      const node = names[key];
      return { w: node?.offsetWidth ?? 0, h: node?.offsetHeight ?? 0 };
    };
    const taken: Box[] = stamp
      ? [
          {
            left: 0,
            top: 0,
            right: stamp.offsetLeft + stamp.offsetWidth,
            bottom: stamp.offsetTop + stamp.offsetHeight
          }
        ]
      : [];
    const rings: Name[] = RINGS.map((km) => ({
      key: `ring ${km}`,
      x: tx,
      y: ty - (km / radar.km_per_px) * k,
      ...size(`ring ${km}`)
    }));
    const others: Name[] = points.map((p) => ({
      key: p.name,
      x: p.x * k,
      y: p.y * k,
      ...size(p.name)
    }));
    spots = place(
      mapSize,
      mapSize,
      taken,
      { key: 'town', x: tx, y: ty, ...size('town') },
      rings,
      others
    );
  });
  // Positions set through the CSSOM, which the policy allows where a style
  // attribute would be refused.
  function at(node: HTMLElement, spot: Spot | undefined) {
    // Hidden, not removed: a name left out keeps its size for the next placing.
    const move = (spot: Spot | undefined) => {
      node.style.visibility = spot ? '' : 'hidden';
      if (spot) {
        node.style.left = `${spot.left}px`;
        node.style.top = `${spot.top}px`;
      }
    };
    move(spot);
    return { update: move };
  }
  function dot(node: HTMLElement, [x, y, shown]: [number, number, boolean]) {
    const move = ([x, y, shown]: [number, number, boolean]) => {
      node.style.visibility = shown ? '' : 'hidden';
      node.style.left = `${x}px`;
      node.style.top = `${y}px`;
    };
    move([x, y, shown]);
    return { update: move };
  }
  const k = $derived(radar && mapSize ? mapSize / radar.frame_width_px : 0);
</script>

{#snippet credit(map: boolean)}
  <p class="credit">
    {t('radar.credit')}{#if map}. {t('radar.basemap_credit')}{/if}
  </p>
{/snippet}

<div bind:this={root} onfocusin={() => data.seeRadar()}>
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
      bind:clientWidth={mapSize}
      aria-label={t('radar.map_label', {
        paese: town,
        ora: frame ? hm(Date.parse(frame.time)) : '',
        sintesi: sentence
      })}
    >
      <!-- One box for the four map layers' colour checks. -->
      <svg
        viewBox="0 0 {width} {height}"
        preserveAspectRatio="none"
        aria-hidden="true"
        data-qa="map-land"
        ><g data-qa="map-water"><g data-qa="map-river"><use href="#under" /></g></g></svg
      >
      <canvas bind:this={canvas} {width} {height}></canvas>
      {#if loading || frame?.missing}<div class="veil" aria-hidden="true"></div>{/if}
      <svg viewBox="0 0 {width} {height}" aria-hidden="true" data-qa="map-border">
        <use href="#over" />
        {#each RINGS as km (km)}
          <circle class="ring" cx={tx} cy={ty} r={km / radar.km_per_px} />
        {/each}
        <circle class="town-ring" cx={tx} cy={ty} r="2" />
        <circle class="town-dot" cx={tx} cy={ty} r="0.8" />
      </svg>
      <div class="names" aria-hidden="true" data-qa="map-label">
        {#each points as p (p.name)}
          <span class="city" use:dot={[p.x * k, p.y * k, spots.has(p.name)]}></span>
          <span class="name" bind:this={names[p.name]} use:at={spots.get(p.name)}>{p.name}</span>
        {/each}
        {#each RINGS as km (km)}
          <span
            class="name ring-name"
            bind:this={names[`ring ${km}`]}
            use:at={spots.get(`ring ${km}`)}>{km} {t('unit.km')}</span
          >
        {/each}
        <span
          class="name here"
          bind:this={names.town}
          bind:clientWidth={townWidth}
          use:at={spots.get('town')}>{town}</span
        >
      </div>
      {#if frame && !loading}
        <div class="stamp" bind:this={stamp}>{hm(Date.parse(frame.time))}</div>
      {/if}
      {#if loading}
        <div class="veil-box"><p>{t('radar.loading')}</p></div>
      {:else if frame?.missing}
        <div class="veil-box">
          <p>{t('radar.frame_missing_box', { ora: hm(Date.parse(frame.time)) })}</p>
        </div>
      {/if}
    </div>
    <div class="timeline">
      <div class="track">
        <div class="ticks" aria-hidden="true">
          {#each radar.frames as f, i (f.time)}
            <i class:on={i === shown} class:miss={f.missing}></i>
          {/each}
        </div>
        <input
          type="range"
          min="0"
          max={last}
          step="1"
          value={shown}
          aria-disabled={loading ? 'true' : undefined}
          oninput={(event) => {
            if (loading) {
              event.currentTarget.value = String(shown);
              return;
            }
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
        <div class="ends" aria-hidden="true">
          <span>{hm(Date.parse(radar.frames[0]?.time ?? ''))}</span>
          <span>{lastTime ? hm(Date.parse(lastTime)) : ''}</span>
        </div>
      </div>
      <button
        class="play"
        type="button"
        aria-disabled={loading ? 'true' : undefined}
        aria-label={playing ? t('radar.pause') : t('radar.play')}
        onclick={toggle}
      >
        <Icon name={playing ? 'pause' : 'play'} />
      </button>
    </div>
    <div class="ramp">
      <p class="vh">{t('radar.legend_title')}</p>
      <div class="steps" aria-hidden="true">
        {#each radar.scale as bin (bin.index)}<i class="r{bin.index}" data-qa="radar-{bin.index}"
          ></i>{/each}
        <i class="nodata"></i>
      </div>
      <div class="bounds" aria-hidden="true">
        {#each radar.scale as bin (bin.index)}<span>{bound(bin.from_mm_h)}</span>{/each}
        <span class="unit">{t('unit.mmh')}</span>
      </div>
      <ul class="words">
        {#each radar.scale as bin (bin.index)}
          <li class:minor={bin.index === 1 || bin.index === 5}>
            <span class="vh">{range(bin)} {t('unit.mmh')}, {className(bin.index)}</span>
            <span class="word" aria-hidden="true">{className(bin.index)}</span>
          </li>
        {/each}
        <li class="nd">{t('radar.legend_nodata')}</li>
      </ul>
    </div>
    {@render credit(true)}
  {/if}
</div>
