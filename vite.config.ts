import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  // jsimgui 0.14.0 has a transposed optional-loader filename. Resolve the
  // published file without patching node_modules (also works after npm ci).
  resolve: { alias: [{ find: './loader-freetype-extensions.js', replacement: './loader-extensions-freetype.js' }] },
  optimizeDeps: { exclude: ['@mori2003/jsimgui'] },
  build: { target: 'es2022' },
});
