import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// SPA estática. En Fase 4 el build se publica en un CDN (Cloudflare Pages / Netlify).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: true },
});
