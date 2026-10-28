import { expect, test } from 'vitest';
import { answer, matches, plainHttp, type Config } from './serve.ts';

const config: Config = {
  trailingSlash: 'never',
  globalHeaders: { 'Cache-Control': 'no-cache', 'X-Frame-Options': 'DENY' },
  routes: [
    { route: '/_app/immutable/*', headers: { 'Cache-Control': 'immutable' } },
    { route: '/.auth/*', statusCode: 404 }
  ]
};
const files = new Set(['/index.html', '/pedrengo.html', '/_app/immutable/a.css']);
const exists = (file: string) => files.has(file);

test('matches a trailing wildcard on the rest of the path only', () => {
  expect(matches('/.auth/*', '/.auth/login/github')).toBe(true);
  expect(matches('/.auth/*', '/.authx')).toBe(false);
  expect(matches('/privacy', '/privacy/')).toBe(false);
});

test('serves a page without its extension', () => {
  expect(answer(config, '/pedrengo', exists)).toMatchObject({
    status: 200,
    file: '/pedrengo.html'
  });
  expect(answer(config, '/', exists).file).toBe('/index.html');
});

test('redirects a trailing slash away', () => {
  expect(answer(config, '/pedrengo/', exists)).toMatchObject({
    status: 301,
    headers: { Location: '/pedrengo' }
  });
});

test('answers a closed route with its status and the global headers', () => {
  expect(answer(config, '/.auth/me', exists)).toEqual({
    status: 404,
    headers: { 'Cache-Control': 'no-cache', 'X-Frame-Options': 'DENY' }
  });
});

test('lets a route header override the global one', () => {
  const { headers } = answer(config, '/_app/immutable/a.css', exists);
  expect(headers['Cache-Control']).toBe('immutable');
  expect(headers['X-Frame-Options']).toBe('DENY');
});

test('answers a missing address with the 404 page and its status', () => {
  const withPage: Config = { ...config, responseOverrides: { '404': { rewrite: '/404.html' } } };
  const has404 = (file: string) => file === '/404.html' || exists(file);
  expect(answer(withPage, '/nope', has404)).toMatchObject({ status: 404, file: '/404.html' });
});

test('sends the global headers with a 404', () => {
  expect(answer(config, '/nope', exists)).toMatchObject({
    status: 404,
    headers: { 'X-Frame-Options': 'DENY' }
  });
});

test('drops only the https upgrade from the policy for plain http', () => {
  const policy = "default-src 'none'; img-src 'self'; upgrade-insecure-requests";
  const plain = plainHttp({ ...config, globalHeaders: { 'Content-Security-Policy': policy } });
  expect(plain.globalHeaders).toEqual({
    'Content-Security-Policy': "default-src 'none'; img-src 'self'"
  });
});
