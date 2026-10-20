// Writes the code the site is built from but the repo does not keep: the
// TypeScript types of the public files, generated from ../schema, the
// Italian strings, read from src/lib/copy/it.md, and the symbol sprite.
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { compile, type JSONSchema } from 'json-schema-to-typescript';
import { BANNED, parse, visible, type Entry } from '../src/lib/copy/parse.ts';
import { favicon, sprite } from '../src/lib/symbols/sprite.ts';

const SCHEMA = '../schema';
const OUT = 'src/generated';

async function types() {
  for (const file of readdirSync(SCHEMA).filter((name) => name.endsWith('.schema.json'))) {
    const schema = JSON.parse(readFileSync(join(SCHEMA, file), 'utf8')) as JSONSchema;
    const ts = await compile(schema, file, {
      bannerComment: '',
      additionalProperties: false,
      strictIndexSignatures: true,
      format: false
    });
    writeFileSync(join(OUT, file.replace('.schema.json', '.ts')), ts);
  }
}

// The checks run here as well as in the tests so that `npm run dev` stops on a
// bad string too, before anyone sees it on a page.
function copy() {
  const { short, long } = parse(readFileSync('src/lib/copy/it.md', 'utf8'));
  const problems = [...short, ...long].flatMap((entry) => {
    const found: string[] = [];
    if (BANNED.test(entry.text)) found.push(`${entry.key}: a character the hooks refuse`);
    if (entry.max !== null && visible(entry.text) > entry.max) {
      found.push(`${entry.key}: ${visible(entry.text)} characters, max ${entry.max}`);
    }
    return found;
  });
  const keys = [...short, ...long].map((entry) => entry.key);
  for (const key of keys.filter((key, i) => keys.indexOf(key) !== i))
    problems.push(`${key}: twice`);
  if (problems.length) throw new Error(`src/lib/copy/it.md:\n${problems.join('\n')}`);

  const module = (name: string, entries: Entry[]) =>
    `export const ${name} = ${JSON.stringify(
      Object.fromEntries(entries.map((entry) => [entry.key, entry.text])),
      null,
      2
    )} as const;\n`;
  writeFileSync(join(OUT, 'copy.ts'), module('copy', short));
  writeFileSync(join(OUT, 'long.ts'), module('long', long));
}

// The sprite's URL carries a hash of its content, so it can be cached for good.
function icons() {
  const svg = sprite();
  writeFileSync('static/icons.svg', svg);
  writeFileSync('static/favicon.svg', favicon());
  const hash = createHash('sha256').update(svg).digest('hex').slice(0, 10);
  writeFileSync(
    join(OUT, 'icons.ts'),
    `export const ICONS = '/icons.svg?v=${hash}';
`
  );
}

mkdirSync(OUT, { recursive: true });
await types();
copy();
icons();
