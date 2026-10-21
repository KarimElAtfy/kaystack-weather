<script lang="ts">
  // The section heading counts the days shown when there are fewer than ten.
  import { t } from '#lib/copy/t.ts';
  import { daysShown } from '#lib/chart/d10.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const daily = $derived(data.forecast.value?.daily);
  const n = $derived(daily ? daysShown(daily).length : null);
</script>

{n !== null && n < 10 ? t('d10.h2_n', { n }) : t('d10.h2')}
