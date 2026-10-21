import { towns } from '#lib/server/towns.ts';

export const load = () => ({ cards: towns() });
