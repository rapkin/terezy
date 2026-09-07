import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  DECLARED_HUE_COLLISIONS,
  EVERY_KIND,
  INSTRUMENT_KIND,
  KINDS,
  VENUE_KIND,
  classWord,
} from "@/design/kinds";
import { SRC } from "../source";

/**
 * SC-002: every kind the API can send has a hue, an icon and a word.
 *
 * The typecheck carries half of it — `INSTRUMENT_KIND` is a mapped type over the instrument
 * read's tag union, so a third declaration kind leaves it one key short and the build red. What
 * the typecheck cannot see is whether the token a style names is **declared**: a map naming
 * `--kind-bond-ink` when the stylesheet declares `--kind-bond-colour` renders a tile with no
 * colour and no error, so the stylesheet is read here.
 */
const STYLES = readFileSync(join(SRC, "styles.css"), "utf8");

const TOKEN = /^var\(--[a-z-]+\)$/;

/** The hue a kind's ink token resolves to, read out of the stylesheet rather than restated. */
function hueOf(reference: string): string {
  const name = reference.slice("var(".length, -1);
  const declaration = new RegExp(`${name}:([^;]*);`).exec(STYLES);
  const hue = /var\((--hue-[a-z-]+)\)/.exec(declaration?.[1] ?? "");
  // An achromatic kind has no hue variable; cash is the only one, and it is chroma 0.
  if (hue === null) return name;
  const value = new RegExp(`${hue[1] ?? ""}:\\s*([0-9.]+)\\s*;`).exec(STYLES);
  if (value === null) throw new Error(`styles.css declares no ${hue[1] ?? "hue"}`);
  return value[1] ?? "";
}

describe("the kind vocabulary", () => {
  it("gives every drawn kind a word, an icon and two declared tokens", () => {
    const kinds = Object.keys(KINDS);
    expect(kinds.length).toBeGreaterThan(0);
    for (const [kind, style] of Object.entries(KINDS)) {
      expect(style.word, `${kind} has no word`).not.toBe("");
      expect(typeof style.Icon, `${kind} has no icon`).toBe("function");
      for (const reference of [style.ink, style.tint]) {
        expect(reference, `${kind} names ${reference}, which is not a token`).toMatch(TOKEN);
        const name = reference.slice("var(".length, -1);
        expect(STYLES, `styles.css declares no ${name}`).toContain(`${name}:`);
      }
    }
  });

  it("maps every instrument read the document declares to one of them", () => {
    const tags = Object.keys(INSTRUMENT_KIND);
    expect(tags.sort()).toEqual([
      "cash.CashDeclaration",
      "fund.FundDeclaration",
      "interface.InstrumentDeclaration",
    ]);
    for (const kind of Object.values(INSTRUMENT_KIND)) {
      expect(Object.keys(KINDS)).toContain(kind);
    }
  });

  it("names the declared classes in words, and renders an unnamed one raw", () => {
    expect(classWord("enumerated_schedule")).toBe("payments enumerated");
    expect(classWord("cash_balance")).toBe("a balance, released at what it was opened with");
    // FR-006: `instrument_class` is `string` in the document, so a class this client has no
    // word for is shown as it arrived. Never blank, never a guess.
    expect(classWord("a_class_nobody_named")).toBe("a_class_nobody_named");
  });

  it("maps every venue kind the document declares to one of them", () => {
    // FR-007's vocabulary, closed in `core/` and refused at load. Nothing on this screen draws a
    // venue; the map binds the language so the graph feature reads a hue rather than choosing one.
    expect(Object.keys(VENUE_KIND).sort()).toEqual([
      "bank",
      "broker",
      "exchange",
      "payroll",
      "platform",
    ]);
    for (const kind of Object.values(VENUE_KIND)) expect(Object.keys(KINDS)).toContain(kind);
  });

  it("gives each kind its own hue, or records why two share one", () => {
    // FR-001's actual requirement, which the icon check below does not reach: two kinds at one
    // hue render in identical ink and tint, and the reader is left counting corners.
    const declared = new Set(DECLARED_HUE_COLLISIONS.map((pair) => [...pair].sort().join("+")));
    const byHue = new Map<string, string[]>();
    for (const kind of EVERY_KIND) {
      const hue = hueOf(KINDS[kind].ink);
      byHue.set(hue, [...(byHue.get(hue) ?? []), kind]);
    }
    const sharing = [...byHue.values()]
      .filter((kinds) => kinds.length > 1)
      .map((kinds) => [...kinds].sort().join("+"));
    expect(sharing.filter((pair) => !declared.has(pair))).toEqual([]);
    // And a collision recorded but no longer real is a stale exception.
    expect([...declared].filter((pair) => !sharing.includes(pair))).toEqual([]);
  });

  it("has one icon per kind and no icon shared between two", () => {
    const icons = new Set(Object.values(KINDS).map((style) => style.Icon));
    expect(icons.size).toBe(EVERY_KIND.length);
  });
});
