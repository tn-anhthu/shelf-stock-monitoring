import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/analyze': 'http://127.0.0.1:3000',
      '/catalog': 'http://127.0.0.1:3000',
      '/confirm': 'http://127.0.0.1:3000',
      '/shelves': 'http://127.0.0.1:3000',
      '/dashboard': 'http://127.0.0.1:3000',
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.js'],
  },
});
