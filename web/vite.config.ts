import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the browser talks to one origin; Vite forwards to the assistant (:8000) and company systems (:9000).
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") },
      "/world": { target: "http://localhost:9000", rewrite: (p) => p.replace(/^\/world/, "") },
    },
  },
});
