<script lang="ts">
  import { ICONS } from '#gen/icons.ts';

  // Always next to text that says the same, so hidden from screen readers.
  let { name, size = 16 }: { name: string; size?: number } = $props();
</script>

<svg
  class="icon"
  width={size}
  height={size}
  viewBox="0 0 16 16"
  aria-hidden="true"
  focusable="false"
>
  <use href="{ICONS}#i-{name}" />
</svg>
