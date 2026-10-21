// The town pages' data blocks, built apart from Kit: Kit prerenders every page
// as plain HTML, and this bundle mounts the blocks into it. Kit's own client
// would add about 17 KB for navigation the site does not need.
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [svelte()],
  base: '/island/',
  build: {
    outDir: 'static/island',
    emptyOutDir: true,
    manifest: true,
    modulePreload: false,
    rolldownOptions: { input: { town: 'src/island/town.ts' } }
  }
});
