<script lang="ts">
  import { ICONS } from '#gen/icons.ts';
  import type { Sky } from './pick.ts';

  // Without a label the symbol is decorative: the same information is in text nearby.
  let { sky, size, label }: { sky: Sky; size: number; label?: string } = $props();
</script>

<svg
  class="sym"
  width={size}
  height={size}
  viewBox="0 0 32 32"
  role={label ? 'img' : undefined}
  aria-label={label}
  aria-hidden={label ? undefined : 'true'}
  focusable="false"
>
  {#if label}<title>{label}</title>{/if}
  <use href="{ICONS}#{sky.base}" />
  {#if sky.drops}<use href="{ICONS}#{sky.drops}" />{/if}
</svg>
