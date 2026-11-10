import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The browser always calls /api on its own origin. In development Vite forwards it to the API;
// in the container nginx does (deploy/nginx.conf). No cross-origin setup is needed.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
