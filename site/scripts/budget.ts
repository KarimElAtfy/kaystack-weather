// Byte budgets on the built site, measured the way a first visit pays for them:
// each page's HTML, plus every script and stylesheet it links, gzipped.
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

export const LIMITS = {
  html: 15_000,
  // A page that loads a script: the town pages, with their data blocks.
  withScript: 60_000,
  withoutScript: 10_000
};

export type Page = { path: string; html: number; js: number; css: number };

const gzipped = (bytes: Buffer) => gzipSync(bytes, { level: 9 }).length;

// Only same-site files count: the build never links anything else.
export function linked(html: string): { js: string[]; css: string[] } {
  const tags = html.match(/<(link|script)\b[^>]*>/g) ?? [];
  const js: string[] = [];
  const css: string[] = [];
  for (const tag of tags) {
    const url = /\b(?:href|src)="([^"]+)"/.exec(tag)?.[1];
    if (!url || /^[a-z]+:/i.test(url) || url.startsWith('//')) continue;
    if (tag.startsWith('<script') || /rel="modulepreload"/.test(tag)) js.push(url);
    else if (/rel="stylesheet"/.test(tag)) css.push(url);
  }
  return { js, css };
}

function htmlFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return htmlFiles(path);
    return entry.name.endsWith('.html') ? [path] : [];
  });
}

export function measure(root: string): Page[] {
  return htmlFiles(root).map((file) => {
    const html = readFileSync(file);
    const { js, css } = linked(html.toString());
    // Root-relative URLs start at the build folder, relative ones at the page.
    const load = (url: string) =>
      readFileSync(url.startsWith('/') ? join(root, url) : resolve(file, '..', url));
    const sum = (urls: string[]) => urls.reduce((total, url) => total + gzipped(load(url)), 0);
    return {
      path: relative(root, file).replaceAll('\\', '/'),
      html: gzipped(html),
      js: sum(js),
      css: sum(css)
    };
  });
}

export function overBudget(page: Page): string[] {
  const problems: string[] = [];
  const limit = page.js > 0 ? LIMITS.withScript : LIMITS.withoutScript;
  if (page.html > LIMITS.html) problems.push(`HTML ${page.html} B over ${LIMITS.html} B`);
  if (page.js + page.css > limit) problems.push(`JS+CSS ${page.js + page.css} B over ${limit} B`);
  return problems;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const pages = measure(process.argv[2] ?? 'build');
  let failed = false;
  for (const page of pages) {
    const problems = overBudget(page);
    failed ||= problems.length > 0;
    const sizes = `html ${page.html}  js ${page.js}  css ${page.css}`;
    console.log(
      `${page.path.padEnd(28)} ${sizes}${problems.length ? '  ' + problems.join('; ') : ''}`
    );
  }
  if (pages.length === 0) {
    console.log('no pages found');
    failed = true;
  }
  process.exit(failed ? 1 : 0);
}
