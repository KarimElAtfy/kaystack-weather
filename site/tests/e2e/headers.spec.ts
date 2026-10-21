import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { expect, test } from '@playwright/test';
import { freezeClock, useScenario, watch } from './fixtures.ts';

const config = JSON.parse(readFileSync('build/staticwebapp.config.json', 'utf8')) as {
  globalHeaders: Record<string, string>;
};

function pages(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return pages(path);
    if (!entry.name.endsWith('.html')) return [];
    const url =
      '/' +
      relative('build', path)
        .replaceAll('\\', '/')
        .replace(/\.html$/, '');
    return [url.replace(/\/?index$/, '') || '/'];
  });
}

for (const url of pages('build')) {
  test(`${url} loads under the policy with no violation`, async ({ page, context, baseURL }) => {
    await useScenario(context, 'pioggia', baseURL ?? '');
    await freezeClock(page);
    const problems = await watch(page);

    const response = await page.goto(url, { waitUntil: 'networkidle' });
    expect(response?.status()).toBe(200);
    expect(response?.headers()['content-security-policy']).toBe(
      config.globalHeaders['Content-Security-Policy']
    );
    expect(problems).toEqual([]);
  });
}

test('the built-in sign-in routes are closed', async ({ request }) => {
  for (const url of ['/.auth/login/github', '/.auth/login/aad', '/.auth/me']) {
    expect((await request.get(url)).status()).toBe(404);
  }
});
