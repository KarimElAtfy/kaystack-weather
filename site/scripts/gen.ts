// Writes the code the site is built from but the repo does not keep: the
// TypeScript types of the public files, generated from ../schema.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { compile, type JSONSchema } from 'json-schema-to-typescript';

const SCHEMA = '../schema';
const OUT = 'src/generated';

async function types() {
  mkdirSync(OUT, { recursive: true });
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

await types();
