// The OpenAPI document, generated rather than read from the repository (owner decision
// 2026-09-05: the document is generated on the fly and is not committed).
//
// One place, because both the type generator and the union-widening test need the same bytes and
// a second invocation is a second answer waiting to disagree with the first.
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const REPO = resolve(WEB, "..");

/** Where a build with no Python -- the container's client stage -- names a document on disk. */
const SUPPLIED = process.env.TEREZY_OPENAPI_JSON;

/** Where a container with no Python and no file reads it from the running API instead. */
const SERVED = process.env.TEREZY_OPENAPI_URL;

/** @returns {Promise<string>} the document, as the bytes a client is generated from. */
export async function openapiDocument() {
  if (SUPPLIED !== undefined) return readFileSync(SUPPLIED, "utf8");
  if (SERVED !== undefined) {
    const answer = await fetch(SERVED);
    if (!answer.ok) throw new Error(`${SERVED} answered ${String(answer.status)}`);
    return await answer.text();
  }
  // `--out` rather than a pipe: the generator writes bytes, and a shell pipeline through Node's
  // stdio is where an encoding or a newline translation would make this a different file from
  // the one the endpoint serves.
  const out = join(mkdtempSync(join(tmpdir(), "terezy-openapi-")), "openapi.json");
  const run = spawnSync(
    "uv",
    ["run", "python", "scripts/generate_openapi.py", "--out", out],
    { cwd: REPO, encoding: "utf8" },
  );
  if (run.error !== undefined || run.status !== 0) {
    const said = run.error === undefined ? run.stderr : run.error.message;
    throw new Error("the OpenAPI generator failed: " + said);
  }
  return readFileSync(out, "utf8");
}
