// Checks that the built site holds nothing meant for development: no fixture
// file, no path to the dev server's /data, no `?now=` clock override. It also
// checks that some script reads the public account the policy allows, so a
// build that reads nothing at all does not pass by accident.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const TEXT = /\.(html|js|css|json|svg|txt|xml)$/;
const BANNED: [RegExp, string][] = [
  [/tests\/fixtures/, 'names the fixtures folder'],
  [/["'`]\/data["'`/]/, 'reads /data from the dev server'],
  [/\.get\(\s*["'`]now["'`]\s*\)/, 'reads the ?now= clock override']
];

function files(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  });
}

const hash = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

// The origin in the policy's connect-src: the only place the site reads data from.
function account(root: string): string | null {
  const config = join(root, 'staticwebapp.config.json');
  if (!existsSync(config)) return null;
  const parsed = JSON.parse(readFileSync(config, 'utf8')) as {
    globalHeaders?: Record<string, string>;
  };
  const policy = parsed.globalHeaders?.['Content-Security-Policy'] ?? '';
  return /connect-src\s+(https:\/\/[^\s;]+)/.exec(policy)?.[1] ?? null;
}

export function problems(root: string, fixtures: string): string[] {
  const built = files(root);
  if (built.length === 0) return [`${root} holds no files`];
  const copies = new Set(files(fixtures).map((file) => hash(readFileSync(file))));
  const found: string[] = [];
  for (const file of built) {
    const path = relative(root, file).replaceAll('\\', '/');
    const bytes = readFileSync(file);
    if (/(^|\/)(fixtures|data)\//.test(path)) found.push(`${path}: a development folder`);
    if (copies.has(hash(bytes))) found.push(`${path}: a copy of a fixture`);
    if (!TEXT.test(path)) continue;
    const text = bytes.toString('utf8');
    for (const [pattern, why] of BANNED) if (pattern.test(text)) found.push(`${path}: ${why}`);
  }
  const origin = account(root);
  const reads = (file: string) =>
    origin !== null && file.endsWith('.js') && readFileSync(file, 'utf8').includes(origin);
  if (!origin) found.push('staticwebapp.config.json names no connect-src origin');
  else if (!built.some(reads)) found.push(`no script reads ${origin}`);
  return found;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const found = problems(process.argv[2] ?? 'build', 'tests/fixtures');
  for (const line of found) console.log(line);
  console.log(
    found.length ? `${found.length} problems` : 'the build holds nothing from development'
  );
  process.exit(found.length ? 1 : 0);
}
