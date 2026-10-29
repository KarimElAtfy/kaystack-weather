<script lang="ts">
  import './symbols.css';
  import { inkLayer, sunLayer } from './layers.ts';
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
  {#if sunLayer(sky.base)}<use href="#{sky.base}-sun" />{/if}
  {#if inkLayer(sky.base)}<use href="#{sky.base}-ink" />{/if}
  {#if sky.drops}<use href="#{sky.drops}" />{/if}
</svg>
