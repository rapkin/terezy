import { describe, expect, it } from "vitest";
import { join } from "node:path";
import { code, modulesUnder, relativeToSrc, SRC } from "../source";

/**
 * SC-010 and FR-005: no module of this screen derives an entity kind from an id, a name or a
 * path.
 *
 * A scan and not a type, because the typecheck cannot see a kind built out of `key.instrument_id`
 * — a prefix test, a `startsWith`, a regular expression over an id — and that is exactly the
 * inference 021 FR-015 already forbids for a category. What the typecheck does carry is the
 * other half: the kind map is exhaustive over the read's tag (`kinds.test.ts`).
 */
const SCANNED = [join(SRC, "answer"), join(SRC, "design")].flatMap(modulesUnder);

/** An identifier being sliced, matched or tested — the shapes a kind is inferred with. */
const INFERRED =
  /\b(?:instrument_id|record_id|venue_id|stream_id|route_id|declared_in|\bname\b)\s*\.\s*(?:startsWith|endsWith|includes|slice|split|match|replace|test)/;

const TESTED_AGAINST_AN_ID = /\b(?:startsWith|endsWith|match|test)\s*\(\s*(?:key|read|record)\b/;

describe("a kind is never inferred", () => {
  it("scans the modules of this screen", () => {
    expect(SCANNED.length).toBeGreaterThan(10);
    expect(SCANNED.map(relativeToSrc).some((path) => path.startsWith("design/kinds"))).toBe(true);
  });

  it("derives no kind from an id, a name or a path", () => {
    const offenders = SCANNED.filter((path) => {
      const body = code(path);
      return INFERRED.test(body) || TESTED_AGAINST_AN_ID.test(body);
    }).map(relativeToSrc);
    expect(offenders).toEqual([]);
  });

  it("would catch one: the scan fires on the shapes it is written against", () => {
    expect(INFERRED.test('const kind = key.instrument_id.startsWith("UA") ? "bond" : "fund";')).toBe(
      true,
    );
    expect(INFERRED.test("const parts = declared_in.split('/');")).toBe(true);
    expect(TESTED_AGAINST_AN_ID.test("if (/^UA/.test(key.instrument_id)) return 'bond';")).toBe(true);
    expect(TESTED_AGAINST_AN_ID.test("if (isDeclared(read.result)) return 'bond';")).toBe(false);
    // The map itself reads a tag, which is a declared field and not an id.
    expect(INFERRED.test('INSTRUMENT_KIND[read.tag]')).toBe(false);
  });
});
