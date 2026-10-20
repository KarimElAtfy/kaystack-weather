<script lang="ts">
  import { has, t } from '#lib/copy/t.ts';

  let { towns, current = null }: { towns: string[]; current?: string | null } = $props();

  const label = (slug: string) => {
    const key = `switch.${slug}`;
    return has(key) ? t(key) : slug;
  };
</script>

<header class="topbar">
  <div class="wrap">
    <div class="brand">
      <a href="/">{t('site.name')}</a>
      <span class="beta" title={t('site.beta_title')}
        >{t('site.beta')}<span class="vh">: {t('site.beta_title')}</span></span
      >
    </div>
    <nav aria-label={t('switch.label')}>
      <div class="switch">
        {#each towns as slug (slug)}
          <a href="/{slug}" aria-current={slug === current ? 'page' : undefined}>{label(slug)}</a>
        {/each}
      </div>
    </nav>
  </div>
</header>
