import { error } from '@sveltejs/kit';
import { islandTags } from '#lib/server/island.ts';
import { towns } from '#lib/server/towns.ts';

export const entries = () => towns().map((town) => ({ town: town.slug }));

export const load = ({ params }: { params: { town: string } }) => {
  const town = towns().find((t) => t.slug === params.town);
  if (!town) error(404, 'No such town');
  return { town, island: islandTags() };
};
