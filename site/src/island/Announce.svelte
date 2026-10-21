<script lang="ts">
  // Says each change of the page's state once, in the hidden role="status"
  // next to the status line. Ages are never in it, so it stays quiet between
  // changes.
  import { t, type Key } from '#lib/copy/t.ts';
  import type { PageState } from '#lib/data/states.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const KEYS: Partial<Record<PageState, Key>> = {
    stale: 'announce.stale',
    old: 'announce.old',
    offline: 'announce.offline',
    failed: 'announce.failed'
  };

  let said = $state('');
  let before: PageState = 'loading';
  $effect(() => {
    const state = data.state;
    if (state === before) return;
    const back = before === 'offline' || before === 'failed';
    before = state;
    const key = KEYS[state] ?? (back ? 'announce.back' : null);
    said = key ? t(key) : '';
  });
</script>

{said}
