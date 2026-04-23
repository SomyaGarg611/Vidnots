import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies API + frame traffic to the Python service so the
// browser sees a single origin — same behaviour as the production
// single-container deploy.
const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/frames": { target: BACKEND, changeOrigin: true },
    },
  },
});
