import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { expect, test } from '@playwright/test';

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
  test(`${url} loads under the policy with no violation`, async ({ page }) => {
    const problems: string[] = [];
    await page.exposeFunction('reportViolation', (text: string) => problems.push(text));
    await page.addInitScript(() => {
      document.addEventListener('securitypolicyviolation', (event) => {
        const report = (window as unknown as { reportViolation: (text: string) => void })
          .reportViolation;
        report(`${event.violatedDirective} ${event.blockedURI}`);
      });
    });
    page.on('console', (message) => {
      if (message.type() === 'error') problems.push(message.text());
    });
    page.on('pageerror', (error) => problems.push(error.message));

    const response = await page.goto(url, { waitUntil: 'load' });
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
