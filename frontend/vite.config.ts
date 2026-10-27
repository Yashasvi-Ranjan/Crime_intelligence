import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// API_TARGET: the live backend; OFFLINE_TARGET: an offline (SAMPLE_MODE) backend that serves /offline-api, as the Vercel function does in production.
// Read from the repo-root .env (real environment variables still win).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '');
  const API_TARGET = env.API_TARGET || 'http://127.0.0.1:8000';
  const OFFLINE_TARGET = env.OFFLINE_TARGET || 'http://127.0.0.1:8001';
  return {
    plugins: [react()],
    server: {
      port: Number(env.PORT) || 5173,
      proxy: {
        '/api': { target: API_TARGET, changeOrigin: true },
        '/offline-api': { target: OFFLINE_TARGET, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/offline-api/, '/api') },
      },
    },
  };
});
