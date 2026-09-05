import { expect, test } from "@playwright/test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * FR-048, as a scan over the suite's own URLs.
 *
 * Necessary rather than decorative: no ordinary assertion can see that a *different* test read
 * the wall clock, and a suite that is deterministic today goes non-deterministic the moment
 * somebody writes one `goto` without a date. The one exception is the redirect suite, which
 * starts from a URL with a parameter missing on purpose and asserts no value.
 */
const HERE = dirname(fileURLToPath(import.meta.url));

const EXEMPT = new Set(["redirect.spec.ts"]);

const GOTO = /page\.goto\(\s*[`"']([^`"']*)/g;

test("every URL a test asserts a figure from carries an explicit as_of", () => {
  const specs = readdirSync(HERE).filter((name) => name.endsWith(".spec.ts"));
  expect(specs.length).toBeGreaterThan(3);

  const offenders: string[] = [];
  for (const spec of specs) {
    if (EXEMPT.has(spec)) continue;
    for (const found of readFileSync(join(HERE, spec), "utf8").matchAll(GOTO)) {
      const url = found[1] ?? "";
      if (!url.includes("as_of=")) offenders.push(`${spec}: ${url}`);
    }
  }
  expect(offenders).toEqual([]);
});

test("the scan would catch one", () => {
  // Assembled rather than written out, so this sample is not itself a call the scan finds.
  const sample = ["page", ".goto(", '"/data/instruments"', ");"].join("");
  const without = [...sample.matchAll(GOTO)].map((held) => held[1]);
  expect(without).toEqual(["/data/instruments"]);
  expect(without[0]?.includes("as_of=")).toBe(false);
});
