// Checks that the built site holds nothing meant for development: no fixture
// file, no path to the dev server's /data, no `?now=` clock override. It also
// checks that some script reads the public account the policy allows, so a
// build that reads nothing at all does not pass by accident. In the sources,
// it keeps colours in tokens.css and breakpoints in layout.css.
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

// The parts not yet rebuilt keep their old rules: layout.css until the layout
// lands, the rest until the cleanup.
const LEGACY = new Set([
  'src/styles/layout.css',
  'src/styles/legacy.css',
  'src/lib/radar/radar.css',
  'src/lib/ui/pages.css'
]);
const COLOUR = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?)\(/i;
const PX_TEXT = /font-size\s*:\s*[\d.]+px/i;
// The user's settings may be asked anywhere; the page's shape only in layout.css.
const PREFERENCE = /^\((?:prefers-[a-z-]+|forced-colors)\s*:\s*[a-z-]+\)$/;
const SHAPE =
  /^\((?:(?:min|max)-width\s*:\s*(?:44|64)em|(?:min|max)-height\s*:\s*(?:32|40)em|orientation\s*:\s*landscape)\)$/;

function styles(file: string): string {
  const text = readFileSync(file, 'utf8');
  if (!file.endsWith('.svelte')) return text;
  // Markup and script blanked line for line, so a problem keeps its line number.
  const blank = (part: string) => part.replace(/[^\n]/g, '');
  return text
    .split(/(<style[^>]*>[\s\S]*?<\/style>)/)
    .map((part) => (part.startsWith('<style') ? part : blank(part)))
    .join('');
}

// Colours in tokens.css only, no font size in px, and media queries only for
// the user's settings or, in layout.css, the agreed breakpoints.
export function styleProblems(root: string, legacy = LEGACY): string[] {
  const found: string[] = [];
  const sources = files(join(root, 'src')).filter((file) => /\.(css|svelte)$/.test(file));
  for (const file of sources) {
    const path = relative(root, file).replaceAll('\\', '/');
    if (legacy.has(path)) continue;
    const name = path.split('/').at(-1);
    styles(file)
      .split('\n')
      .forEach((line, i) => {
        const at = `${path}:${i + 1}`;
        const code = line.replace(/\/\*.*?\*\//g, '');
        // Declarations only: a selector such as #ade55o is not a colour.
        const value = /^\s*[a-z-]+\s*:(.*)$/i.exec(code)?.[1] ?? '';
        if (!code.trimEnd().endsWith('{') && name !== 'tokens.css' && COLOUR.test(value)) {
          found.push(`${at}: a colour outside tokens.css`);
        }
        if (PX_TEXT.test(code)) found.push(`${at}: a font size in px`);
        const media = /@media\s+([^{]+)/.exec(code)?.[1];
        for (const feature of media?.match(/\([^()]*\)/g) ?? []) {
          const shape = name === 'layout.css' && SHAPE.test(feature);
          if (!PREFERENCE.test(feature) && !shape) {
            found.push(`${at}: ${feature} is not an agreed breakpoint`);
          }
        }
      });
  }
  return found;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const found = [...problems(process.argv[2] ?? 'build', 'tests/fixtures'), ...styleProblems('.')];
  for (const line of found) console.log(line);
  console.log(
    found.length
      ? `${found.length} problems`
      : 'the build holds nothing from development, the styles keep to the tokens'
  );
  process.exit(found.length ? 1 : 0);
}
