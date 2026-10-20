// The tags that load the town pages' bundle: from its build manifest, or in
// development straight from the source, which Kit's dev server compiles.
import { readFileSync } from 'node:fs';

const ENTRY = 'src/island/town.ts';

export function islandTags(): string {
  if (import.meta.env.DEV) return `<script type="module" src="/${ENTRY}"></script>`;
  const manifest = JSON.parse(readFileSync('static/island/.vite/manifest.json', 'utf8')) as Record<
    string,
    { file: string; css?: string[] }
  >;
  const entry = manifest[ENTRY];
  if (!entry) throw new Error(`${ENTRY} is not in the island manifest`);
  return [
    ...(entry.css ?? []).map((file) => `<link rel="stylesheet" href="/island/${file}">`),
    `<script type="module" src="/island/${entry.file}"></script>`
  ].join('');
}
