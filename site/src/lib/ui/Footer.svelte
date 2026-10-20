<script lang="ts">
  import { t } from '#lib/copy/t.ts';

  // The town pages fill the sources list and the time of the last read.
  let { live = false }: { live?: boolean } = $props();
</script>

<footer class="site-foot">
  <div class="wrap">
    <div class="cols">
      <div>
        {#if live}<div id="sources"></div>{/if}
        <p class="space">{t('footer.credits')}</p>
      </div>
      <div>
        <nav>
          <ul>
            <li>
              <a href="https://github.com/KarimElAtfy/kaystack-weather">{t('footer.code')}</a>
            </li>
          </ul>
        </nav>
        <p class="space">{t('footer.beta')}</p>
        {#if live}<p class="xsmall" id="refreshed"></p>{/if}
      </div>
    </div>
  </div>
</footer>
