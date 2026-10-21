// Takes out of build/ what no visitor needs. The island's build manifest is
// read while Kit prerenders. Kit's __data.json files feed its client router,
// which every page here turns off; they also put a folder next to each page's
// .html file, which would leave Static Web Apps two ways to answer /pedrengo.
import { readdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';

rmSync('build/island/.vite', { recursive: true, force: true });

function prune(dir: string) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      prune(path);
      if (readdirSync(path).length === 0) rmSync(path, { recursive: true });
    } else if (entry.name === '__data.json') {
      rmSync(path);
    }
  }
}
prune('build');
