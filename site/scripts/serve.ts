// Serves the build the way the Static Web App does for the parts of
// staticwebapp.config.json this site uses, so the browser tests run under the
// real headers. vite preview can't: it leaves custom headers off prerendered pages.
import { createServer } from 'node:http';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { extname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

type Route = { route: string; statusCode?: number; headers?: Record<string, string> };
export type Config = {
  trailingSlash?: 'always' | 'never' | 'auto';
  globalHeaders?: Record<string, string>;
  routes?: Route[];
  responseOverrides?: Record<string, { rewrite?: string }>;
};
export type Answer = { status: number; headers: Record<string, string>; file?: string };

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp'
};

// The platform's wildcard: a trailing * matches the rest of the path.
export function matches(pattern: string, path: string): boolean {
  return pattern.endsWith('*') ? path.startsWith(pattern.slice(0, -1)) : path === pattern;
}

// The first matching route wins, as on the platform.
export function answer(config: Config, path: string, exists: (file: string) => boolean): Answer {
  const headers = { ...config.globalHeaders };
  const route = config.routes?.find((r) => matches(r.route, path));
  if (route?.statusCode) return { status: route.statusCode, headers };
  if (config.trailingSlash === 'never' && path.length > 1 && path.endsWith('/')) {
    return { status: 301, headers: { ...headers, Location: path.slice(0, -1) } };
  }
  const candidates = path.endsWith('/')
    ? [`${path}index.html`]
    : [path, `${path}.html`, `${path}/index.html`];
  const file = candidates.find(exists);
  if (!file) {
    // The platform answers a missing address with the 404 page, still as a 404.
    const page = config.responseOverrides?.['404']?.rewrite;
    if (page && exists(page)) {
      return {
        status: 404,
        headers: { ...headers, 'Content-Type': TYPES['.html'] ?? '' },
        file: page
      };
    }
    return { status: 404, headers };
  }
  const type = TYPES[extname(file)] ?? 'application/octet-stream';
  return { status: 200, headers: { ...headers, ...route?.headers, 'Content-Type': type }, file };
}

// WebKit applies upgrade-insecure-requests to localhost as well and asks for
// https://localhost, so for it the policy goes without that one directive.
export function plainHttp(config: Config): Config {
  const policy = config.globalHeaders?.['Content-Security-Policy'];
  if (!policy) return config;
  const kept = policy
    .split(';')
    .map((directive) => directive.trim())
    .filter((directive) => directive && directive !== 'upgrade-insecure-requests');
  return {
    ...config,
    globalHeaders: { ...config.globalHeaders, 'Content-Security-Policy': kept.join('; ') }
  };
}

export function serve(root: string, port: number, http = false) {
  const base = resolve(root);
  const read = JSON.parse(readFileSync(join(base, 'staticwebapp.config.json'), 'utf8')) as Config;
  const config = http ? plainHttp(read) : read;
  const inside = (path: string) => {
    const full = resolve(base, `.${path}`);
    return full.startsWith(base + sep) && existsSync(full) && statSync(full).isFile();
  };
  return createServer((request, response) => {
    const path = decodeURIComponent(new URL(request.url ?? '/', 'http://site').pathname);
    const { status, headers, file } = answer(config, path, inside);
    response.writeHead(status, headers);
    response.end(
      file && request.method !== 'HEAD' ? readFileSync(resolve(base, `.${file}`)) : undefined
    );
  }).listen(port);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.argv[3] ?? 4173);
  serve(process.argv[2] ?? 'build', port, process.argv[4] === '--http');
  console.log(`http://localhost:${port}`);
}
