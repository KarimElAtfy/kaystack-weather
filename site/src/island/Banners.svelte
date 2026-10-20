<script lang="ts">
  // Problems that touch the whole page, at most two. This sits in a live
  // region, so its text changes only when the data does, never with the clock.
  import { t } from '#lib/copy/t.ts';
  import { forecastFreshness, metarFreshness, sourceState } from '#lib/data/states.ts';
  import Icon from '#lib/symbols/Icon.svelte';
  import { ago, dayName, hm } from '#lib/time.ts';
  import type { TownData } from './town.svelte.ts';

  let { data }: { data: TownData } = $props();

  const readings = $derived([data.now, data.forecast]);
  const offline = $derived(readings.some((r) => r.problem === 'offline'));
  const failed = $derived(
    !offline && readings.some((r) => r.problem === 'unavailable' || r.problem === 'invalid')
  );
  const forecast = $derived(data.forecast.value);
  const freshness = $derived(
    forecast ? forecastFreshness(forecast, data.forecast.at ?? data.clock) : 'fresh'
  );
  const metar = $derived(data.now.value?.metar);

  // A stale block is the moment to learn which source is down.
  $effect(() => {
    if (freshness !== 'fresh' || (metar && metarFreshness(metar, data.clock) !== 'fresh')) {
      data.askStatus();
    }
  });

  const cause = $derived.by(() => {
    const source = data.status.value?.sources['open-meteo'];
    if (!source?.checked_at || sourceState('open-meteo', source, data.clock) !== 'down') return '';
    return ` ${t('state.cause_openmeteo', { ora: hm(Date.parse(source.checked_at)) })}`;
  });

  const banners = $derived.by(() => {
    const out: { kind: 'warn' | 'bad'; icon: string; text: string }[] = [];
    const last = data.lastRead;
    if (offline && last !== null)
      out.push({ kind: 'warn', icon: 'off', text: t('state.offline', { ora: hm(last) }) });
    if (failed) {
      const since = last !== null ? ` ${t('state.fetch_failed_since', { ora: hm(last) })}` : '';
      out.push({ kind: 'warn', icon: 'warn', text: t('state.fetch_failed') + since });
    }
    if (forecast && freshness !== 'fresh') {
      const issued = Date.parse(forecast.issued_at);
      const at = data.forecast.at ?? data.clock;
      out.push(
        freshness === 'expired'
          ? {
              kind: 'bad',
              icon: 'bad',
              text:
                t('state.forecast_old', { giorno: dayName(issued, at), ora: hm(issued) }) + cause
            }
          : {
              kind: 'warn',
              icon: 'warn',
              text: t('state.forecast_stale', { ora: hm(issued), fa: ago(issued, at) }) + cause
            }
      );
    }
    return out.slice(0, 2);
  });
</script>

{#each banners as banner (banner.text)}
  <div class="banner {banner.kind}">
    <Icon name={banner.icon} />
    <p>{banner.text}</p>
  </div>
{/each}
