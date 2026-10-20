import { expect, test } from 'vitest';
import { answer, matches, type Config } from './serve.ts';

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

test('sends the global headers with a 404', () => {
  expect(answer(config, '/nope', exists)).toMatchObject({
    status: 404,
    headers: { 'X-Frame-Options': 'DENY' }
  });
});
