import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { Ajv2020 } from 'ajv/dist/2020.js';
import { expect, test } from 'vitest';

const ajv = new Ajv2020({ validateFormats: false, allErrors: true });
const validators = Object.fromEntries(
  ['now', 'forecast', 'radar', 'status'].map((name) => [
    `${name}.json`,
    ajv.compile(JSON.parse(readFileSync(`../schema/${name}.schema.json`, 'utf8')))
  ])
);

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? files(join(dir, entry.name))
      : entry.name.endsWith('.json')
        ? [join(dir, entry.name)]
        : []
  );
}

const fixtures = files('tests/fixtures');

test('covers every scenario and file', () => {
  expect(fixtures.length).toBe(26);
});

for (const file of fixtures) {
  const name = relative('tests/fixtures', file).replaceAll('\\', '/');
  test(`${name} follows the schema`, () => {
    const validate = validators[file.split(/[\\/]/).pop() ?? ''];
    expect(validate).toBeDefined();
    validate!(JSON.parse(readFileSync(file, 'utf8')));
    expect(validate!.errors ?? []).toEqual([]);
  });
}

test('names an existing sprite in every radar file', () => {
  for (const file of fixtures.filter((f) => f.endsWith('radar.json'))) {
    const { sprite } = JSON.parse(readFileSync(file, 'utf8')) as { sprite: string };
    expect(() => readFileSync(join(file, '..', sprite))).not.toThrow();
  }
});
