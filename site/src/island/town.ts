// Mounts the data blocks into the prerendered town page.
import { mount, type Component } from 'svelte';
import { browserEnv } from '#lib/data/source.ts';
import { TownData, type TownInfo } from './town.svelte.ts';
import Issued from './Issued.svelte';
import Refreshed from './Refreshed.svelte';

const main = document.querySelector<HTMLElement>('[data-town]');
if (main?.dataset.town) {
  const data = new TownData(JSON.parse(main.dataset.town) as TownInfo, browserEnv());
  const place = (id: string, block: Component<{ data: TownData }>) => {
    const target = document.getElementById(id);
    if (!target) return;
    target.replaceChildren();
    mount(block, { target, props: { data } });
  };
  place('issued', Issued);
  place('refreshed', Refreshed);
}
