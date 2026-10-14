/// <reference types="vitest/config" />
import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Only `make web` and `npm run build` read this: deployed, nothing runs Vite, and the API serves the build itself
export default defineConfig({
  // Local and the build
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  // Local only: /api goes to the API that `make web` runs beside Vite
  server: {
    port: 5173,
    proxy: { '/api': `http://localhost:${process.env.API_PORT ?? 8000}` },
  },
  // Tests only
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
  },
});
