<script lang="ts">
  // Six cells two hours apart under the verdict. Static: the 48 hours below
  // are where an hour is looked at closely.
  import { t } from '#lib/copy/t.ts';
  import { deg } from '#lib/format.ts';
  import type { Cell } from '#lib/data/ahead.ts';
  import Sky from '#lib/symbols/Sky.svelte';
  import { skyAlt } from '#lib/symbols/words.ts';
  import { hm } from '#lib/time.ts';

  let { cells }: { cells: Cell[] } = $props();
</script>

<ol class="strip" aria-label={t('strip.label')} data-qa="strip">
  {#each cells as cell (cell.time)}
    <li>
      <span class="when">{hm(cell.time)}</span>
      <Sky sky={cell.sky} size={28} label={skyAlt(cell.sky, cell.rainy, cell.counted)} />
      <span class="t">{deg(cell.temp)}</span>
      <!-- Always there, empty when dry, so a wet cell does not grow the row. -->
      <span class="n" aria-hidden="true"
        >{cell.rainy ? t('models.of', { n: cell.rainy, m: cell.counted }) : ''}</span
      >
    </li>
  {/each}
</ol>

<style>
  @layer blocks {
    .strip {
      container: strip / inline-size;
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      row-gap: var(--space-3);
    }
    li {
      display: grid;
      justify-items: center;
      gap: var(--space-1);
      font-size: var(--text-s);
      text-align: center;
    }
    .when {
      color: var(--ink-2);
    }
    .t {
      font-weight: 600;
    }
    .n {
      min-block-size: 1.4em;
      font-size: var(--text-xs);
    }
    /* In rem, so the symbols grow with the text instead of staying 28 px. */
    li :global(.sym) {
      inline-size: 1.75rem;
      block-size: 1.75rem;
    }
    @container strip (width < 20em) {
      li {
        grid-column: span 2;
      }
    }
  }
</style>
