import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// The dev server is the same-origin half of FR-033: the browser talks to one origin here as it
// does in production, so no cross-origin allowance is needed in either mode.
const API_ORIGIN = process.env.TEREZY_API_ORIGIN ?? "http://127.0.0.1:8000";

/**
 * Say where /api goes, on the way up.
 *
 * A proxy to an API that is not running answers 500 with a body that is not this API's, and the
 * screen then reports an API that did not answer — true, and one step removed from the fact that
 * settles it, which is the origin the requests were being sent to.
 */
function announcesTheApi() {
  const say = () => {
    process.stdout.write(`  \u001b[32m\u27a4\u001b[0m  /api      \u2192 ${API_ORIGIN}\n`);
  };
  return { name: "terezy:announce-api", configureServer: say, configurePreviewServer: say };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), announcesTheApi()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": { target: API_ORIGIN, changeOrigin: false },
    },
  },
  // The preview server proxies too, so the end-to-end suite sees one origin over the built
  // output exactly as the production container serves it.
  preview: {
    host: "127.0.0.1",
    proxy: {
      "/api": { target: API_ORIGIN, changeOrigin: false },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
