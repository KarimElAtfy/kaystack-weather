import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from 'vitest';
import { problems, styleProblems } from './guard.ts';

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

const svelte = `<p>x</p>
<style>
  .t {
    color: #fff;
    font-size: 12px;
  }
  #ade {
    color: var(--ink);
  }
</style>`;

test('keeps colours in tokens.css and px out of font sizes', () => {
  const root = folder({
    'src/styles/tokens.css': ':root {\n  --ink: #1c1b18;\n}',
    'src/island/Now.svelte': svelte,
    'src/lib/x.css': '.a {\n  border: 1px solid rgba(0, 0, 0, 0.1);\n}'
  });
  expect(styleProblems(root, new Set())).toEqual([
    'src/island/Now.svelte:4: a colour outside tokens.css',
    'src/island/Now.svelte:5: a font size in px',
    'src/lib/x.css:2: a colour outside tokens.css'
  ]);
});

test('allows the agreed breakpoints in layout.css only', () => {
  const root = folder({
    'src/styles/layout.css': `@media (max-width: 44em) and (min-height: 32em) {
}
@media (min-width: 1024px) {
}`,
    'src/lib/y.css': `@media (min-width: 64em) {
}
@media (prefers-reduced-motion: reduce) {
}`
  });
  expect(styleProblems(root, new Set())).toEqual([
    'src/lib/y.css:1: (min-width: 64em) is not an agreed breakpoint',
    'src/styles/layout.css:3: (min-width: 1024px) is not an agreed breakpoint'
  ]);
});
