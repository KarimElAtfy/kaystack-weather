<script lang="ts">
  import { t } from '#lib/copy/t.ts';
  import { ago, dayName, hm, ymd } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();
  const issued = $derived(data.forecast.value ? Date.parse(data.forecast.value.issued_at) : null);
</script>

{#if issued !== null}
  {@const when = {
    ora: hm(issued),
    fa: ago(issued, data.clock),
    giorno: dayName(issued, data.clock)
  }}
  {ymd(issued) === ymd(data.clock) ? t('trust.issued', when) : t('trust.issued_day', when)}
{:else if data.forecast.problem}
  {t('state.forecast_missing')}
{:else}
  {t('state.loading')}
{/if}
