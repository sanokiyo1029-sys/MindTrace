import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const examWorker = {
  name: 'exam-worker',
  apply: (_config, env) => env.command === 'build' && env.mode !== 'android',
  enforce: 'post',
  generateBundle(_options, bundle) {
    const assets = Object.keys(bundle).filter(name => name.startsWith('assets/')).sort().map(name => '/' + name);
    const script = readFileSync(new URL('./exam-sw.js', import.meta.url), 'utf8');
    const version = createHash('sha256').update(JSON.stringify(assets)).update(script)
      .update(String(bundle['index.html']?.source || '')).digest('hex').slice(0, 16);
    this.emitFile({ type: 'asset', fileName: 'exam-sw.js', source:
      `const CACHE = 'mindtrace-exam-shell-${version}';\nconst ASSETS = new Set(${JSON.stringify(assets)});\n${script}` });
  },
};

export default defineConfig({
  plugins: [react(), examWorker],
  envDir: '..', // one .env at the repo root (docs/INTEGRATION.md)
  // allowedHosts: a Cloudflare quick tunnel to the dev server would otherwise get Vite's "Blocked request" page
  server: { allowedHosts: ['.trycloudflare.com'], proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
});
