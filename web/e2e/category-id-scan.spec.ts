import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join, relative } from "node:path";
import ts from "typescript";
import { WEB } from "../tools/openapi.mjs";
import { modulesUnder } from "../tests/source";
import { AS_OF } from "./offline";

/**
 * FR-015 and SC-012: `web/src` names no category id the running API's own index returns.
 *
 * The id list comes from the API rather than from a constant here, because a hard-coded list
 * would be the second copy this check exists to forbid. It runs inside the end-to-end job for
 * that reason and no other -- the API is already up.
 *
 * **The match rule is part of the requirement.** Thirteen of the ids are ordinary English words
 * and the client's own layout puts every route module under `src/routes/`, so a substring grep
 * would fire on files that hard-code nothing. It therefore matches string and template literals
 * only, parsed rather than grepped, and skips a literal that is an import specifier or a path
 * segment of the file's own path.
 */
const SRC = join(WEB, "src");
const EXCEPTIONS = join(WEB, "tools", "category-scan-exceptions.txt");

function exceptions(): readonly string[] {
  return readFileSync(EXCEPTIONS, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "" && !line.startsWith("#"));
}

/** Every string and template literal in one module, minus the ones that name a module. */
function literalsIn(path: string): readonly string[] {
  const parsed = ts.createSourceFile(
    path,
    readFileSync(path, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const found: string[] = [];
  const specifiers = new Set<ts.Node>();
  const walk = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      if (node.moduleSpecifier !== undefined) specifiers.add(node.moduleSpecifier);
    }
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const first = node.arguments[0];
      if (first !== undefined) specifiers.add(first);
    }
    if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
      !specifiers.has(node)
    ) {
      found.push(node.text);
    }
    ts.forEachChild(node, walk);
  };
  walk(parsed);
  return found;
}

function names(literal: string, id: string, own: readonly string[]): boolean {
  if (own.includes(id)) return false;
  return literal === id || literal.split("/").includes(id);
}

test("no module under web/src names a category id outside the checked-in exception list", async ({
  request,
}) => {
  const answer = await request.get(`/api/registry?as_of=${AS_OF}`);
  expect(answer.ok()).toBe(true);
  const body: { categories: { category: string }[] } = await answer.json();
  const indexed = body.categories.map((held) => held.category);
  expect(indexed.length).toBeGreaterThan(20);

  const permitted = exceptions();
  const offenders: string[] = [];
  for (const path of modulesUnder(SRC)) {
    const relativePath = relative(WEB, path).split("\\").join("/");
    const own = relativePath.split("/");
    for (const literal of literalsIn(path)) {
      for (const id of indexed) {
        if (names(literal, id, own) && !permitted.includes(relativePath)) {
          offenders.push(`${relativePath}: ${JSON.stringify(literal)} names ${id}`);
        }
      }
    }
  }
  expect(offenders).toEqual([]);
});

test("the exception list holds no module under /data/, and the scan would catch one", () => {
  const permitted = exceptions();
  expect(permitted.length).toBeGreaterThan(0);
  expect(permitted.filter((path) => path.includes("/data/"))).toEqual([]);

  expect(names("official-rates", "official-rates", ["src", "routes", "series-map.ts"])).toBe(true);
  expect(names("/api/cpi", "cpi", ["src", "api", "queries.ts"])).toBe(true);
  expect(names("series.CpiSeries", "cpi", ["src", "components", "series", "identity.ts"])).toBe(false);
  expect(names("routes", "routes", ["src", "routes", "tree.ts"])).toBe(false);
});
