import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { expect, test } from 'vitest';
import { LIMITS, linked, measure, overBudget } from './budget.ts';

function site(files: Record<string, string | Buffer>): string {
  const root = mkdtempSync(join(tmpdir(), 'budget-'));
  for (const [path, body] of Object.entries(files)) {
    mkdirSync(join(root, path, '..'), { recursive: true });
    writeFileSync(join(root, path), body);
  }
  return root;
}

test('finds scripts, module preloads and stylesheets, not other links', () => {
  const html = `
    <link rel="icon" href="/favicon.svg">
    <link href="./_app/a.css" rel="stylesheet">
    <link rel="modulepreload" href="/island/b.js">
    <script type="module" src="/island/c.js"></script>
    <link rel="stylesheet" href="https://example.org/x.css">`;
  expect(linked(html)).toEqual({ js: ['/island/b.js', '/island/c.js'], css: ['./_app/a.css'] });
});

test('resolves relative links from the page folder', () => {
  const root = site({
    'come-funziona/index.html': '<link href="../_app/a.css" rel="stylesheet">',
    '_app/a.css': 'body { margin: 0 }'
  });
  const [page] = measure(root);
  expect(page?.path).toBe('come-funziona/index.html');
  expect(page?.css).toBeGreaterThan(0);
});

test('holds a page without scripts to the lower limit', () => {
  const noise = randomBytes(LIMITS.withoutScript + 1000);
  const root = site({
    'index.html': '<link href="/big.css" rel="stylesheet">',
    'big.css': noise
  });
  const [page] = measure(root);
  expect(overBudget(page!)).toHaveLength(1);
});

test('gives a page with a script the higher limit', () => {
  const root = site({
    'pedrengo.html': '<script type="module" src="/island/town.js"></script>',
    'island/town.js': randomBytes(LIMITS.withoutScript + 1000)
  });
  const [page] = measure(root);
  expect(overBudget(page!)).toEqual([]);
});
