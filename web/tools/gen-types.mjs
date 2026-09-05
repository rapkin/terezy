// The typed contract, generated at every gate and committed nowhere.
//
// Owner decision 2026-09-05: nothing derived from the document is committed either, so the gate
// FR-003 asked for -- regenerate and diff against the committed output -- becomes "generation
// succeeds and `tsc` then passes over what came out".
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { openapiDocument, WEB } from "./openapi.mjs";

const OUTPUT = join(WEB, "src", "api", "schema.d.ts");

const scratch = join(mkdtempSync(join(tmpdir(), "terezy-openapi-")), "openapi.json");
writeFileSync(scratch, await openapiDocument(), "utf8");

const emitted = spawnSync(
  join(WEB, "node_modules", ".bin", "openapi-typescript"),
  [scratch, "--output", OUTPUT],
  { cwd: WEB, encoding: "utf8", stdio: "inherit" },
);
if (emitted.status !== 0) {
  process.stderr.write("openapi-typescript refused the generated document.\n");
  process.exit(1);
}
