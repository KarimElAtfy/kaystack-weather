import { existsSync, readFileSync, statSync } from 'node:fs';
import { resolve, sep } from 'node:path';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

const ACCOUNT = 'https://stkaystackmeteopubprod.blob.core.windows.net';
const FIXTURES = resolve('tests/fixtures');

// In development the pages read /data. `npm run dev -- --mode pioggia` answers
// it from tests/fixtures/pioggia; plain `npm run dev` passes it on to the
// public account, so real data shows without widening its CORS rule.
/** @returns {import('vite').Plugin} */
function data() {
  return {
    name: 'meteo-data',
    apply: 'serve',
    configureServer(server) {
      const scenario = resolve(FIXTURES, server.config.mode);
      if (!scenario.startsWith(FIXTURES + sep) || !existsSync(scenario)) return;
      server.middlewares.use('/data', (request, response) => {
        const file = resolve(
          scenario,
          `.${decodeURIComponent((request.url ?? '/').split('?')[0] ?? '/')}`
        );
        if (!file.startsWith(scenario + sep) || !existsSync(file) || !statSync(file).isFile()) {
          response.statusCode = 404;
          response.end();
          return;
        }
        response.setHeader(
          'Content-Type',
          file.endsWith('.json') ? 'application/json' : 'image/png'
        );
        response.end(readFileSync(file));
      });
    }
  };
}

export default defineConfig({
  plugins: [data(), sveltekit({ adapter: adapter() })],
  server: {
    proxy: {
      '/data': {
        target: ACCOUNT,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/data/, '/public')
      }
    }
  },
  test: {
    include: ['src/**/*.test.ts', 'scripts/**/*.test.ts', 'tests/unit/**/*.test.ts'],
    environment: 'node',
    // Far from Rome, so a time printed in the machine's zone fails the tests.
    env: { TZ: 'America/New_York' }
  }
});
