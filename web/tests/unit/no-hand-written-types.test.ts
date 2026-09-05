import { describe, expect, it } from "vitest";
import { code, modulesUnder, relativeToSrc, SRC, text } from "../source";

/**
 * FR-005, as a scan over the tree rather than only as a lint rule.
 *
 * Necessary rather than decorative: the lint rule can be switched off at one site with an inline
 * comment, and a cast is FR-004 switched off at that site -- so the scan is what stops one being
 * added quietly. It reads code with comments and string literals removed, so prose about casting
 * does not fire it.
 */
const MODULES = modulesUnder(SRC);

/** A wire record's tag is `<module>.<Name>`; a client-side discriminant's never is. */
const WIRE_TAG_DECLARATION = /\btag\s*[?]?\s*:\s*["'][A-Za-z_]+\.[A-Za-z_]+["']/;

const ANGLED_ASSERTION = /(^|[=(,:[{]\s*)<[A-Z][\w.]*>\s*[a-z_$]/m;

describe("no hand-written response type, and no cast over one", () => {
  it("scans a tree that actually has modules in it", () => {
    expect(MODULES.length).toBeGreaterThan(20);
  });

  it("declares no response type outside the generated document", () => {
    const offenders = MODULES.filter(
      (path) => !relativeToSrc(path).startsWith("api/schema") && WIRE_TAG_DECLARATION.test(text(path)),
    ).map(relativeToSrc);
    expect(offenders).toEqual([]);
  });

  it("contains no cast and no type assertion", () => {
    const offenders = MODULES.filter((path) => {
      const body = code(path);
      // The angle-bracket assertion is illegal in `.tsx`, so it is only looked for in `.ts`;
      // the delimiter before it is what separates one from `queryOptions<Answered>(`.
      const angled = path.endsWith(".ts") && ANGLED_ASSERTION.test(body);
      return /\bas\s+(?!const\b)[A-Z{[]/.test(body) || angled;
    }).map(relativeToSrc);
    expect(offenders).toEqual([]);
  });

  it("would catch one: the scan fires on the shapes it is written against", () => {
    expect(WIRE_TAG_DECLARATION.test('type Body = { tag: "envelopes.ReadOfInstruments" };')).toBe(true);
    expect(WIRE_TAG_DECLARATION.test('type State = { tag: "unverified" };')).toBe(false);
    expect(/\bas\s+(?!const\b)[A-Z{[]/.test("return body as Registry;")).toBe(true);
    expect(/\bas\s+(?!const\b)[A-Z{[]/.test("const TAGS = [1] as const;")).toBe(false);
    expect(ANGLED_ASSERTION.test("const held = <Registry>body;")).toBe(true);
    expect(ANGLED_ASSERTION.test("return queryOptions<Answered>({ queryKey: [] });")).toBe(false);
  });
});
