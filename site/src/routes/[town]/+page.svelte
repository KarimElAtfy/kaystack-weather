<script lang="ts">
  import { around, has, t } from '#lib/copy/t.ts';
  import { km } from '#lib/format.ts';
  import Header from '#lib/ui/Header.svelte';
  import Footer from '#lib/ui/Footer.svelte';

  let { data } = $props();
  const town = $derived(data.town);
  const named = (key: string) => (has(key) ? t(key) : town.slug);
  const name = $derived(named(`town.${town.slug}`));
  const station = $derived(around('trust.station', 'stazione', { km: km(town.km) }));
  const sections = [
    ['adesso', 'nav.now'],
    ['ore-48', 'nav.h48'],
    ['giorni-10', 'nav.d10'],
    ['radar', 'nav.radar']
  ] as const;
</script>

<svelte:head>
  <title>{t('site.title_town', { paese: name })}</title>
  <meta name="description" content={t('site.description')} />
  <!-- Built from the island manifest at build time; no data ever reaches it. -->
  {@html data.island}
</svelte:head>

<a class="skip" href="#main">{t('site.skip')}</a>
<Header towns={data.towns} current={town.slug} />

<main id="main" data-town={JSON.stringify(town)}>
  <div class="wrap">
    <div class="town-head">
      <h1>{name} <span class="prov">{named(`town.province.${town.slug}`)}</span></h1>
      <p class="trust">
        {station[0]}<strong>{town.station}</strong>{station[1]}
        <a href="/come-funziona#stazione">{t('trust.why')}</a>
        <span id="statusline">{t('state.loading')}</span>
      </p>
      <p id="announce" class="vh" role="status"></p>
    </div>
  </div>

  <nav class="sections" aria-label={t('nav.label')}>
    <div class="wrap">
      {#each sections as [id, key] (id)}
        <a href="#{id}">{t(key)}</a>
      {/each}
    </div>
  </nav>

  <div class="wrap">
    <div class="layout">
      <section id="adesso" class="panel" aria-labelledby="h-adesso">
        <div class="sec-head">
          <h2 id="h-adesso">{t('now.h2')}</h2>
          <span class="kind">{t('now.measured')}</span>
        </div>
        <div id="adesso-body" class="skel skel-now">{t('state.loading')}</div>
      </section>
      <section id="ore-48" class="panel" aria-labelledby="h-ore48">
        <div class="sec-head">
          <h2 id="h-ore48">{t('h48.h2')}</h2>
          <span class="kind">{t('h48.forecast')}</span>
        </div>
        <div id="ore48-body" class="skel skel-48">{t('state.loading')}</div>
      </section>
      <section id="giorni-10" class="panel" aria-labelledby="h-giorni10">
        <div class="sec-head">
          <h2 id="h-giorni10">{t('d10.h2')}</h2>
          <span class="kind">{t('h48.forecast')}</span>
        </div>
        <div id="giorni10-body" class="skel skel-10">{t('state.loading')}</div>
      </section>
      <section id="radar" class="panel" aria-labelledby="h-radar">
        <div class="sec-head">
          <h2 id="h-radar">{t('radar.h2')}</h2>
          <span class="kind">{t('now.measured_short')}</span>
        </div>
        <p class="sec-meta">{t('radar.sub')}</p>
        <div id="radar-body" class="skel skel-radar">{t('state.loading')}</div>
      </section>
    </div>
  </div>
  <noscript>
    <div class="wrap"><p class="note">{t('state.noscript')}</p></div>
  </noscript>
</main>

<Footer live />
<!-- Built at prerender from the symbol code and the pipeline's map. -->
<div class="sprite" aria-hidden="true">{@html data.sprites}</div>
