// FR-036, FR-054: every absolute URL in a build output, checked against a listed allowlist.
//
// Over the built output rather than over the sources, because the case it exists for is a
// dependency that reaches somewhere at run time despite what its row in the dependency table
// says -- and that URL appears in the bundle and nowhere else.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ALLOWLIST = join(HERE, "bundle-url-allowlist.txt");

const TEXT = /\.(js|mjs|cjs|css|html|json|map|svg|txt|webmanifest)$/;
const URLS = /\b(?:https?:|wss?:)\/\/[^\s"'`)\\<>{}]+/g;

/** @param {string} root @returns {string[]} */
function filesUnder(root) {
  const found = [];
  for (const entry of readdirSync(root)) {
    const path = join(root, entry);
    if (statSync(path).isDirectory()) found.push(...filesUnder(path));
    else if (TEXT.test(entry)) found.push(path);
  }
  return found;
}

/** @returns {Set<string>} */
function allowed() {
  const lines = readFileSync(ALLOWLIST, "utf8").split("\n");
  return new Set(
    lines.map((line) => line.trim()).filter((line) => line !== "" && !line.startsWith("#")),
  );
}

/** @param {string} root @returns {{url: string, file: string}[]} */
export function unlistedUrls(root) {
  const listed = allowed();
  const offenders = [];
  for (const file of filesUnder(root)) {
    for (const found of readFileSync(file, "utf8").matchAll(URLS)) {
      const url = found[0].replace(/[.,;:]+$/, "");
      if (!listed.has(url)) offenders.push({ url, file: relative(root, file) });
    }
  }
  return offenders;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = resolve(process.argv[2] ?? "dist");
  const offenders = unlistedUrls(root);
  for (const offender of offenders) {
    process.stderr.write(`unlisted absolute URL ${offender.url} in ${offender.file}\n`);
  }
  if (offenders.length > 0) {
    process.stderr.write(
      String(offenders.length) + ` absolute URL(s) in ${root} are not in ${ALLOWLIST}. FR-035 forbids a ` +
        "request to any origin but this application's own; add a line with a reason only for a " +
        "URL nothing fetches.\n",
    );
    process.exit(1);
  }
  process.stdout.write(`no unlisted absolute URL in ${root}\n`);
}
