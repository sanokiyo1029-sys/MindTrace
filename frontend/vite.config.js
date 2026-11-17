import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  envDir: '..', // one .env at the repo root (docs/INTEGRATION.md)
  server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
});
