import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from 'vitest';
import { problems } from './guard.ts';

const ORIGIN = 'https://account.example.net';
const CONFIG = JSON.stringify({
  globalHeaders: { 'Content-Security-Policy': `default-src 'none'; connect-src ${ORIGIN}` }
});

function folder(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), 'guard-'));
  for (const [path, body] of Object.entries(files)) {
    mkdirSync(join(root, path, '..'), { recursive: true });
    writeFileSync(join(root, path), body);
  }
  return root;
}

const fixtures = folder({ 'pioggia/v1/now.json': '{"schema":"now/1"}' });
const clean = {
  'staticwebapp.config.json': CONFIG,
  'index.html': '<p>Meteo</p>',
  'island/assets/town.js': `fetch("${ORIGIN}/public/v1/pedrengo/now.json")`
};

test('passes a build that only reads the account', () => {
  expect(problems(folder(clean), fixtures)).toEqual([]);
});

test('finds a fixture copied into the build, under any name', () => {
  const root = folder({ ...clean, 'radar/now.json': '{"schema":"now/1"}' });
  expect(problems(root, fixtures)).toEqual(['radar/now.json: a copy of a fixture']);
});

test('finds development folders and paths', () => {
  const root = folder({
    ...clean,
    'data/v1/status.json': '{}',
    'island/assets/dev.js': 'const DATA = "/data"; fetch(`/data/v1/x.json`)'
  });
  expect(problems(root, fixtures)).toEqual([
    'data/v1/status.json: a development folder',
    'island/assets/dev.js: reads /data from the dev server'
  ]);
});

test('finds the clock override and the fixtures folder named in a script', () => {
  const root = folder({
    ...clean,
    'island/assets/clock.js': 'new URLSearchParams(location.search).get("now")',
    'island/assets/path.js': 'import("../tests/fixtures/pioggia/now.json")'
  });
  expect(problems(root, fixtures)).toEqual([
    'island/assets/clock.js: reads the ?now= clock override',
    'island/assets/path.js: names the fixtures folder'
  ]);
});

test('fails a build in which no script reads the account', () => {
  const root = folder({ 'staticwebapp.config.json': CONFIG, 'index.html': '<p>Meteo</p>' });
  expect(problems(root, fixtures)).toEqual([`no script reads ${ORIGIN}`]);
});

test('fails an empty or missing build', () => {
  expect(problems(join(tmpdir(), 'guard-none'), fixtures)).toEqual([
    `${join(tmpdir(), 'guard-none')} holds no files`
  ]);
});
