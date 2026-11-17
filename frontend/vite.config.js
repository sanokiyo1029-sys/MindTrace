import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  envDir: '..', // one .env at the repo root (docs/INTEGRATION.md)
  // allowedHosts: a Cloudflare quick tunnel to the dev server would otherwise get Vite's "Blocked request" page
  server: { allowedHosts: ['.trycloudflare.com'], proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
});
