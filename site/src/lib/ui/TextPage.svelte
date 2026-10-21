<script lang="ts">
  import '#lib/ui/pages.css';
  import { long } from '#gen/long.ts';
  import { has, t, type Key } from '#lib/copy/t.ts';
  import Header from '#lib/ui/Header.svelte';
  import Footer from '#lib/ui/Footer.svelte';

  let { towns, name, title }: { towns: string[]; name: string; title: Key } = $props();

  // Paragraphs and headings of the page, in the order of the copy file. A key
  // whose last part starts with h_ is a heading; "stazione" is the anchor the
  // town pages link to.
  const ANCHORS: Record<string, string> = { station: 'stazione' };
  const blocks = $derived(
    Object.entries(long)
      .filter(([key]) => key.startsWith(`page.${name}.`))
      .map(([key, text]) => {
        const last = key.split('.').pop() ?? '';
        const heading = last.startsWith('h_') ? last.slice(2) : null;
        return { key, text, id: heading ? (ANCHORS[heading] ?? heading) : null };
      })
  );
  const back = $derived(
    JSON.stringify(
      Object.fromEntries(
        towns.map((slug) => {
          const key = `town.${slug}`;
          return [slug, t('page.back', { paese: has(key) ? t(key) : slug })];
        })
      )
    )
  );
</script>

<svelte:head>
  <title>{t(title)} | {t('site.name')}</title>
  <meta name="towns" content={towns.join(' ')} />
  {@html '<script src="/remember.js" defer></script>'}
</svelte:head>

<a class="skip" href="#main">{t('site.skip')}</a>
<Header {towns} />

<main id="main" class="wrap">
  <article class="prose">
    <a class="back" href="/" hidden data-back={back}>{t('site.name')}</a>
    <h1>{t(title)}</h1>
    {#each blocks as block (block.key)}
      {#if block.id}<h2 id={block.id}>{block.text}</h2>{:else}<p>{block.text}</p>{/if}
    {/each}
  </article>
</main>

<Footer />
