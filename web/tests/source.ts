import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { WEB } from "../tools/openapi.mjs";

export const SRC = join(WEB, "src");

export function modulesUnder(root: string): readonly string[] {
  const found: string[] = [];
  for (const entry of readdirSync(root)) {
    const path = join(root, entry);
    if (statSync(path).isDirectory()) found.push(...modulesUnder(path));
    else if (/\.tsx?$/.test(entry) && !entry.endsWith(".d.ts")) found.push(path);
  }
  return found;
}

export function relativeToSrc(path: string): string {
  return relative(SRC, path).split("\\").join("/");
}

/**
 * The module's text with comments, string literals and import statements removed.
 *
 * Imports go too, because `import { Refusal as RefusalValue }` is an alias and not a cast, and a
 * scan that cannot tell the two apart gets silenced by exceptions until it holds nothing.
 */
export function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/^\s*import[\s\S]*?;\s*$/gm, " ")
    .replace(/^\s*export\s+(type\s+)?\{[\s\S]*?\}\s*from[^;]*;\s*$/gm, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ")
    .replace(/"(?:[^"\\\n]|\\.)*"/g, '""')
    .replace(/'(?:[^'\\\n]|\\.)*'/g, "''")
    .replace(/`(?:[^`\\]|\\.)*`/g, "``");
}

export function text(path: string): string {
  return readFileSync(path, "utf8");
}
