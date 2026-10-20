<script lang="ts">
  import '#lib/ui/pages.css';
  import { has, t } from '#lib/copy/t.ts';
  import { km } from '#lib/format.ts';
  import Header from '#lib/ui/Header.svelte';
  import Footer from '#lib/ui/Footer.svelte';

  let { data } = $props();
  const named = (key: string, fallback: string) => (has(key) ? t(key) : fallback);
</script>

<svelte:head>
  <title>{t('site.title_home')}</title>
  <meta name="description" content={t('site.description')} />
  <meta name="towns" content={data.towns.join(' ')} />
  <!-- Blocking on purpose: it may leave for the remembered town before the page paints. -->
  {@html '<script src="/remember.js"></script>'}
</svelte:head>

<a class="skip" href="#main">{t('site.skip')}</a>
<Header towns={data.towns} />

<main id="main" class="wrap home">
  <h1>{t('home.h1')}</h1>
  <p class="intro">{t('home.intro')}</p>
  <div class="towns">
    {#each data.cards as town (town.slug)}
      <a class="towncard" href="/{town.slug}">
        <span class="name">
          {named(`town.${town.slug}`, town.slug)}
          <span class="prov">{named(`town.province.${town.slug}`, '')}</span>
        </span>
        <span class="ref">{t('home.ref', { stazione: town.station, km: km(town.km) })}</span>
      </a>
    {/each}
  </div>
</main>

<Footer />
