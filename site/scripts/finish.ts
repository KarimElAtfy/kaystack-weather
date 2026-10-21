// The island's build manifest is read while Kit prerenders and is of no use
// once the site is built, so it does not ship.
import { rmSync } from 'node:fs';

rmSync('build/island/.vite', { recursive: true, force: true });
