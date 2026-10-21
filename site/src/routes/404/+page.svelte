<script lang="ts">
  import '#lib/ui/pages.css';
  import { has, t } from '#lib/copy/t.ts';
  import Header from '#lib/ui/Header.svelte';
  import Footer from '#lib/ui/Footer.svelte';

  // The page the Static Web App sends, with a 404, for any address it does not have.
  let { data } = $props();
  const label = (slug: string) => {
    const key = `switch.${slug}`;
    return has(key) ? t(key) : slug;
  };
</script>

<svelte:head>
  <title>{t('page.404.title')} | {t('site.name')}</title>
</svelte:head>

<a class="skip" href="#main">{t('site.skip')}</a>
<Header towns={data.towns} />

<main id="main" class="wrap">
  <article class="prose">
    <h1>{t('page.404.title')}</h1>
    <p>{t('page.404.p1')}</p>
    <p>
      {t('page.404.p2')}
      {#each data.towns as slug, i (slug)}{i ? ', ' : ' '}<a href="/{slug}">{label(slug)}</a
        >{/each}.
    </p>
  </article>
</main>

<Footer />
