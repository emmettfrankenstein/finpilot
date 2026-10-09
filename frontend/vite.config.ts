/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The dev server proxies /api to Django so the browser sees one origin:
// the refresh cookie stays SameSite=Strict and no CORS is needed.
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: apiTarget, changeOrigin: false } },
  },
  preview: {
    port: 4173,
    proxy: { '/api': { target: apiTarget, changeOrigin: false } },
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: { manualChunks: { charts: ['recharts'], vendor: ['react', 'react-dom', 'react-router-dom'] } },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
