import { describe, expect, it } from "vitest";
import { join } from "node:path";
import { code, modulesUnder, relativeToSrc, SRC } from "../source";

/**
 * SC-004, as a scan over `src/card/`.
 *
 * Necessary rather than decorative: the typecheck cannot see arithmetic over two served amounts —
 * `a.amount - b.amount` is two numbers to it — and a bar computed that way is a figure with no
 * owning call and no test on either side of the wire. Every bar's amount must be a field the API
 * sent.
 */
const CARD = join(SRC, "card");
const MODULES = modulesUnder(CARD);

/** Arithmetic whose operand is a served `Money.amount`, in either position. */
const DERIVED = /\.amount\s*[-+*/]|[-+*/]=?\s*[\w.]*\.amount\b/;

describe("no bar is the difference of two served figures", () => {
  it("scans a tree that actually has modules in it", () => {
    expect(MODULES.length).toBeGreaterThan(4);
  });

  it("performs no arithmetic over a served amount anywhere under src/card/", () => {
    const offenders = MODULES.filter((path) => DERIVED.test(code(path))).map(relativeToSrc);
    expect(offenders).toEqual([]);
  });

  it("would catch one: the scan fires on the expressions the rule names", () => {
    expect(DERIVED.test("  const bar = outlay.amount - arrived.amount;")).toBe(true);
    expect(DERIVED.test("  return released.amount - charge.amount;")).toBe(true);
    expect(DERIVED.test("  total += bar.amount;")).toBe(true);
    expect(DERIVED.test("  const held = bar.amount;")).toBe(false);
    expect(DERIVED.test("  if (amount.amount !== 0) return held;")).toBe(false);
  });
});
