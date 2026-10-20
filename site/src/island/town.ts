// Mounts the data blocks into the prerendered town page.
import { mount, type Component } from 'svelte';
import { browserEnv } from '#lib/data/source.ts';
import { TownData, type TownInfo } from './town.svelte.ts';
import Adesso from './Adesso.svelte';
import Banners from './Banners.svelte';
import D10 from './D10.svelte';
import H48 from './H48.svelte';
import Issued from './Issued.svelte';
import Refreshed from './Refreshed.svelte';
import Sources from './Sources.svelte';

const main = document.querySelector<HTMLElement>('[data-town]');
if (main?.dataset.town) {
  const data = new TownData(JSON.parse(main.dataset.town) as TownInfo, browserEnv());
  const place = (id: string, block: Component<{ data: TownData }>) => {
    const target = document.getElementById(id);
    if (!target) return;
    // The block draws its own placeholder, the same as the prerendered one.
    target.replaceChildren();
    target.classList.remove(...[...target.classList].filter((name) => name.startsWith('skel')));
    mount(block, { target, props: { data } });
  };
  place('issued', Issued);
  place('refreshed', Refreshed);
  place('adesso-body', Adesso);
  place('ore48-body', H48);
  place('giorni10-body', D10);
  place('banners', Banners);
  place('sources', Sources);
}
