import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';

const text = readFileSync('static/staticwebapp.config.json', 'utf8');
const config = JSON.parse(text) as {
  globalHeaders: Record<string, string>;
  routes: { route: string; statusCode?: number; headers?: Record<string, string> }[];
  navigationFallback?: unknown;
};
const headers = config.globalHeaders;
const csp = new Map(
  (headers['Content-Security-Policy'] ?? '').split(';').map((part) => {
    const [name = '', ...values] = part.trim().split(/\s+/);
    return [name, values] as const;
  })
);

test('stays under the 20 KB the platform accepts', () => {
  expect(Buffer.byteLength(text)).toBeLessThan(20 * 1024);
});

test('allows no inline code and nothing from other sites', () => {
  expect(headers['Content-Security-Policy']).not.toMatch(/unsafe-|\*|data:|blob:/);
  expect(csp.get('default-src')).toEqual(["'none'"]);
  expect(csp.get('script-src')).toEqual(["'self'"]);
  expect(csp.get('style-src')).toEqual(["'self'"]);
  expect(csp.get('img-src')).toEqual(["'self'"]);
  expect(csp.get('frame-ancestors')).toEqual(["'none'"]);
  expect(csp.get('require-trusted-types-for')).toEqual(["'script'"]);
});

test('reads data only from the public account', () => {
  expect(csp.get('connect-src')).toEqual(['https://stkaystackmeteopubprod.blob.core.windows.net']);
});

test('sends the security headers on every response', () => {
  expect(
    Number(/max-age=(\d+)/.exec(headers['Strict-Transport-Security'] ?? '')?.[1])
  ).toBeGreaterThanOrEqual(31536000);
  expect(headers['X-Content-Type-Options']).toBe('nosniff');
  expect(headers['Referrer-Policy']).toBe('no-referrer');
  expect(headers['X-Frame-Options']).toBe('DENY');
  expect(headers['Permissions-Policy']).toContain('geolocation=()');
});

test('closes the built-in sign-in routes', () => {
  const auth = config.routes.filter((route) => route.route.startsWith('/.auth/'));
  expect(auth.map((route) => route.route)).toContain('/.auth/*');
  expect(auth.every((route) => route.statusCode === 404)).toBe(true);
});

// With a fallback the platform answers unknown paths, the closed /.auth ones
// included, with the fallback page and a 200.
test('has no navigation fallback', () => {
  expect(config.navigationFallback).toBeUndefined();
});

test('caches only content-hashed files for good', () => {
  const forever = config.routes.filter((route) =>
    route.headers?.['Cache-Control']?.includes('immutable')
  );
  expect(forever.map((route) => route.route)).toEqual([
    '/_app/immutable/*',
    '/island/assets/*',
    '/icons.svg'
  ]);
  expect(headers['Cache-Control']).toBe('no-cache');
});
