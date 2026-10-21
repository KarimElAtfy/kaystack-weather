<script lang="ts">
  // The status line under the station sentence: the issue time, or the state
  // of the whole page when something is wrong. It keeps two lines of room at
  // every width, so a change of state never moves the page. It is not a live
  // region, since its ages change every minute; Announce says the changes.
  import { t } from '#lib/copy/t.ts';
  import { metarFreshness } from '#lib/data/states.ts';
  import Icon from '#lib/symbols/Icon.svelte';
  import { ago, dayName, hm, ymd } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const state = $derived(data.state);
  const metar = $derived(data.now.value?.metar);

  // A late block is the moment to learn which source is down, for the list of
  // sources, which then opens by itself.
  $effect(() => {
    if (
      state === 'stale' ||
      state === 'old' ||
      (metar && metarFreshness(metar, data.clock) !== 'fresh')
    ) {
      data.askStatus();
    }
  });

  const line = $derived.by((): { kind: 'plain' | 'warn' | 'bad'; text: string } => {
    const last = data.lastRead;
    const forecast = data.forecast.value;
    const issued = forecast ? Date.parse(forecast.issued_at) : null;
    const at = data.forecast.at ?? data.clock;
    switch (state) {
      case 'offline':
        return last === null
          ? { kind: 'warn', text: t('status.failed_none') }
          : { kind: 'warn', text: t('status.offline', { ora: hm(last) }) };
      case 'failed':
        return last === null
          ? { kind: 'warn', text: t('status.failed_none') }
          : { kind: 'warn', text: t('status.failed', { ora: hm(last) }) };
      case 'missing':
        return { kind: 'bad', text: t('status.missing') };
      case 'loading':
        return { kind: 'plain', text: t('state.loading') };
    }
    if (issued === null) return { kind: 'plain', text: t('state.loading') };
    const when = { ora: hm(issued), fa: ago(issued, data.clock), giorno: dayName(issued, at) };
    if (state === 'old') return { kind: 'bad', text: t('status.old', when) };
    if (state === 'stale') return { kind: 'warn', text: t('status.stale', when) };
    return {
      kind: 'plain',
      text: ymd(issued) === ymd(data.clock) ? t('status.ok', when) : t('status.ok_day', when)
    };
  });
</script>

{#if line.kind === 'plain'}{line.text}{:else}<span class={line.kind}
    ><Icon name={line.kind} size={14} />{line.text}</span
  >{/if}
