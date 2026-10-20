<script lang="ts">
  // The state of each source, from status.json. It is read when someone opens
  // the list, or when a block turns stale, and the list then opens by itself
  // if a source other than ARPA, late by design, is not up to date.
  import { has, t } from '#lib/copy/t.ts';
  import { SOURCES, sourceState } from '#lib/data/states.ts';
  import Icon from '#lib/symbols/Icon.svelte';
  import { ago, hm } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const rows = $derived.by(() => {
    const sources = data.status.value?.sources;
    if (!sources) return [];
    return SOURCES.flatMap((name) => {
      const source = sources[name];
      const label = `footer.src.${name}`;
      if (!source || !has(label)) return [];
      const at = source.data_time ? Date.parse(source.data_time) : null;
      const time =
        at === null ? '' : t('footer.status_row', { ora: hm(at), fa: ago(at, data.clock) });
      const note = name === 'arpa' ? t('footer.src.arpa_note') : '';
      return [
        {
          name,
          label: t(label),
          state: sourceState(name, source, data.clock),
          detail: [time, note].filter(Boolean).join('. ')
        }
      ];
    });
  });
  const trouble = $derived(rows.some((row) => row.name !== 'arpa' && row.state !== 'ok'));
  let open = $state(false);
  $effect(() => {
    if (trouble) open = true;
  });
  const STATE = {
    ok: 'footer.status_ok',
    late: 'footer.status_late',
    down: 'footer.status_down'
  } as const;
  const ICON = { ok: 'ok', late: 'warn', down: 'bad' } as const;
</script>

<details bind:open ontoggle={(event) => event.currentTarget.open && data.askStatus()}>
  <summary>{t('footer.status_h2')}</summary>
  {#if rows.length}
    <ul class="srcs">
      {#each rows as row (row.name)}
        <li>
          <span class="st {row.state}"
            ><Icon name={ICON[row.state]} size={12} />{t(STATE[row.state])}</span
          >
          <span>{row.label}</span>
          <span class="d">{row.detail}</span>
        </li>
      {/each}
    </ul>
  {:else if open}
    <p class="xsmall">{data.status.problem ? t('state.fetch_failed') : t('state.loading')}</p>
  {/if}
</details>
