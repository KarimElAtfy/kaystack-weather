import { has, t } from '#lib/copy/t.ts';
import { models } from '#lib/format.ts';
import type { Sky } from './pick.ts';

export function skyName(sky: Sky): string {
  const key = `sky.${sky.key}`;
  return has(key) ? t(key) : '';
}

// "Coperto. Pioggia: 8 modelli su 10." for a symbol in a table.
export const skyAlt = (sky: Sky, rainy: number, counted: number) =>
  t('sky.alt', { cielo: skyName(sky), modelli: models(rainy, counted) });
