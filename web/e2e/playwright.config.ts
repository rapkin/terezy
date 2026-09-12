import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * FR-045: the suite runs against the real API on loopback over a composed data root, with no
 * network reachable.
 *
 * The client is served by Vite's preview server over the built output and proxies `/api` to the
 * API process, so the browser sees one origin exactly as it does in production. Both processes
 * are started here rather than by the job, so `pnpm e2e` and CI run the same thing.
 *
 * **The root is `tests/data_roots.py`'s composed one, not the checkout's `data/`.** The default
 * root includes `data/user/`, which is gitignored: it holds the owner's real position on his
 * machine and nothing at all in every other checkout, so a screen drawn from it is a different
 * screen per machine.
 */
const API_PORT = Number(process.env.TEREZY_API_PORT ?? 8123);
const WEB_PORT = Number(process.env.TEREZY_WEB_PORT ?? 4173);

/** Named for the port so two lanes on different ports do not compose into one directory. */
const DATA_ROOT = join(tmpdir(), `terezy-e2e-data-root-${String(API_PORT)}`);

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
      command:
        `uv run python -m tests.data_roots --materialise ${DATA_ROOT} && ` +
        `uv run python -m terezy.api.http --host 127.0.0.1 --port ${String(API_PORT)}`,
      // The repository root, so the suite starts the API the way web/README.md tells a person
      // to, and so `tests.data_roots` is importable. `uv` walks up to the project and the built
      // client is located from the package (`api/http/roots`).
      cwd: "../..",
      env: { TEREZY_DATA_ROOT: DATA_ROOT },
      url: `http://127.0.0.1:${String(API_PORT)}/api/cpi?as_of=2026-01-01`,
      // Never reused, unlike the client below: reuse skips `command`, so a process left on this
      // port by an interrupted run answers from whatever root it was started over — the stale
      // materialised one, or the checkout's `data/` with his overlay in it. A port already in
      // use fails the run instead, which is the outcome this whole change is for.
      reuseExistingServer: false,
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
