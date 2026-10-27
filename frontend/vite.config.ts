import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// API_TARGET: the live backend; OFFLINE_TARGET: an offline (SAMPLE_MODE) backend that serves /offline-api, as the Vercel function does in production.
const API_TARGET = process.env.API_TARGET || 'http://127.0.0.1:8000';
const OFFLINE_TARGET = process.env.OFFLINE_TARGET || 'http://127.0.0.1:8001';

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/offline-api': { target: OFFLINE_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/offline-api/, '/api') },
    },
  },
});
