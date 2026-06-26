import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Web-only dev server (no Electron). Use for testing the UI in a browser:
//   pnpm dev:web   →   http://localhost:5173/
// File pickers / "open folder" need Electron, so those buttons are no-ops here;
// everything else talks to the backend over HTTP (127.0.0.1:8757).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
