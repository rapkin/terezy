import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    // The lint tests write a probe module into `src/` -- which is where the rules they exercise
    // apply -- and the source scans read `src/`. Run in parallel, one sees the other's probe.
    fileParallelism: false,
    css: false,
  },
});
