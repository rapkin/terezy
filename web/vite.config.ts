import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// The dev server is the same-origin half of FR-033: the browser talks to one origin here as it
// does in production, so no cross-origin allowance is needed in either mode.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.TEREZY_API_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  // The preview server proxies too, so the end-to-end suite sees one origin over the built
  // output exactly as the production container serves it.
  preview: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: process.env.TEREZY_API_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
