import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server proxies the API to the Python backend; production builds go into the Python package.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../facevision/web', emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8600' },
      '/ws': { target: 'ws://127.0.0.1:8600', ws: true },
    },
  },
  test: { environment: 'jsdom' },
} as any);
