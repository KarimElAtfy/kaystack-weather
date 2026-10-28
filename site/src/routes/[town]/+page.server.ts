import { readFileSync } from 'node:fs';
import { error } from '@sveltejs/kit';
import { islandTags } from '#lib/server/island.ts';
import { towns } from '#lib/server/towns.ts';
import { sprite } from '#lib/symbols/sprite.ts';

export const entries = () => towns().map((town) => ({ town: town.slug }));

export const load = ({ params }: { params: { town: string } }) => {
  const town = towns().find((t) => t.slug === params.town);
  if (!town) error(404, 'No such town');
  // The symbols and the base map go into the page itself, not a file read by
  // <use>, so that their classes take the page's tokens in every engine.
  const map = readFileSync(`src/lib/radar/maps/${town.slug}.svg`, 'utf8');
  return { town, island: islandTags(), sprites: sprite() + map };
};
