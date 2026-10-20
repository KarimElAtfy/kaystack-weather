<script lang="ts">
  import { t } from '#lib/copy/t.ts';
  import { hm } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();
</script>

{#if data.lastRead !== null}{t('state.refreshed', { ora: hm(data.lastRead) })}{/if}
