import { defineConfig, devices } from "@playwright/test";

/**
 * FR-045: the suite runs against the real API on loopback over the shipped `data/`, with no
 * network reachable.
 *
 * The client is served by Vite's preview server over the built output and proxies `/api` to the
 * API process, so the browser sees one origin exactly as it does in production. Both processes
 * are started here rather than by the job, so `pnpm e2e` and CI run the same thing.
 */
const API_PORT = Number(process.env.TEREZY_API_PORT ?? 8123);
const WEB_PORT = Number(process.env.TEREZY_WEB_PORT ?? 4173);

export const BASE_URL = `http://127.0.0.1:${String(WEB_PORT)}`;

export default defineConfig({
  testDir: ".",
  fullyParallel: true,
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  // The API is one uvicorn process and the registry read is megabytes over the shipped tree,
  // so more workers than this queue behind it and time out on the server rather than on the
  // screen. Measured 2026-09-05: six workers turned three 20-second reads into three failures.
  workers: 3,
  reporter: process.env.CI !== undefined ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 60_000,
  // The registry read is megabytes over the shipped tree, so the default five seconds is a
  // measurement of the machine rather than of the screen.
  expect: { timeout: 30_000 },
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // terezy's own entry point, never a bare server command: it is the one that applies the
      // bind guard before it binds (020 FR-026b).
      command: `uv run python -m terezy.api.http --host 127.0.0.1 --port ${String(API_PORT)}`,
      // The repository root, because the API's data root defaults to `data/` relative to the
      // process's directory and a server started elsewhere answers 500 rather than refusing.
      cwd: "../..",
      url: `http://127.0.0.1:${String(API_PORT)}/api/cpi?as_of=2026-01-01`,
      reuseExistingServer: process.env.CI === undefined,
      timeout: 120_000,
    },
    {
      command: `node_modules/.bin/vite preview --host 127.0.0.1 --port ${String(WEB_PORT)} --strictPort`,
      cwd: "..",
      url: BASE_URL,
      reuseExistingServer: process.env.CI === undefined,
      timeout: 120_000,
      env: { TEREZY_API_ORIGIN: `http://127.0.0.1:${String(API_PORT)}` },
    },
  ],
});
