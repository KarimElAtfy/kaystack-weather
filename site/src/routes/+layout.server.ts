import { towns } from '#lib/server/towns.ts';

export const load = () => ({ towns: towns().map((town) => town.slug) });
