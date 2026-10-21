// Mounts the data blocks into the prerendered town page.
import { mount, type Component } from 'svelte';
import { browserEnv } from '#lib/data/source.ts';
import { TownData, type TownInfo } from './town.svelte.ts';
import Adesso from './Adesso.svelte';
import Announce from './Announce.svelte';
import D10 from './D10.svelte';
import H48 from './H48.svelte';
import Refreshed from './Refreshed.svelte';
import Sources from './Sources.svelte';
import Status from './Status.svelte';

// Marks the section being read in the section bar. On wide screens the radar
// sits in its own column and is never "the" section being read.
function sectionBar() {
  const links = [...document.querySelectorAll<HTMLAnchorElement>('.sections a')];
  const sections = links.map((link) => document.getElementById(link.hash.slice(1)));
  const mark = () => {
    const wide = window.matchMedia('(min-width: 1024px)').matches;
    let current = sections[0];
    for (const section of sections) {
      if (
        section &&
        !(wide && section.id === 'radar') &&
        section.getBoundingClientRect().top < 120
      ) {
        current = section;
      }
    }
    links.forEach((link, i) => link.setAttribute('aria-current', String(sections[i] === current)));
  };
  window.addEventListener('scroll', mark, { passive: true });
  mark();
}

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
  place('statusline', Status);
  place('announce', Announce);
  place('refreshed', Refreshed);
  place('adesso-body', Adesso);
  place('ore48-body', H48);
  place('giorni10-body', D10);
  place('sources', Sources);
  sectionBar();
}
