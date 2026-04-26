import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite proxies /api and /media to the Django backend so we don't need CORS in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
  build: {
    outDir: "../backend/frontend_dist",
    emptyOutDir: true,
  },
});
