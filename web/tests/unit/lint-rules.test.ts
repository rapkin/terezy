import { describe, expect, it } from "vitest";
import { join } from "node:path";
import { WEB } from "../../tools/openapi.mjs";
import { messagesFor, messagesIn } from "../lint";

/**
 * The rules are asserted by running them, not by reading the configuration.
 *
 * A rule that is present and configured off is FR-004 and FR-021a switched off everywhere at
 * once, and a test that only reads the config file cannot tell the two apart.
 */
describe("the lint rules that carry a requirement", () => {
  it("fails a `default` arm on a discriminated-union switch (FR-004, risk R1)", async () => {
    const messages = await messagesFor(`
type Two = { tag: "a" } | { tag: "b" };
export function pick(value: Two): string {
  switch (value.tag) {
    case "a":
      return "a";
    case "b":
      return "b";
    default:
      return "anything else";
  }
}
`);
    expect(messages.join("\n")).toMatch(/default/i);
  }, 60_000);

  it("fails a switch that leaves a union member unhandled", async () => {
    const messages = await messagesFor(`
type Two = { tag: "a" } | { tag: "b" };
export function pick(value: Two): string {
  switch (value.tag) {
    case "a":
      return "a";
  }
  return "";
}
`);
    expect(messages.join("\n")).toMatch(/switch|exhaust/i);
  }, 60_000);

  it("fails a second clock read anywhere under src/ (FR-021a)", async () => {
    const now = await messagesFor(`export const at = new Date().toISOString();\n`);
    expect(now.join("\n")).toContain("src/clock.ts");
    const stamp = await messagesFor(`export const at = Date.now();\n`);
    expect(stamp.join("\n")).toContain("src/clock.ts");
  }, 60_000);

  it("permits the one clock read, in the module listed as the exception", async () => {
    const messages = await messagesIn(join(WEB, "src", "clock.ts"));
    expect(messages).toEqual([]);
  }, 60_000);

  it("fails a cast over a value (FR-005), and permits `as const`", async () => {
    const cast = await messagesFor(`
export function widen(body: unknown): { tag: string } {
  return body as { tag: string };
}
`);
    expect(cast.join("\n")).toContain("FR-005");
    const literal = await messagesFor(`export const TAGS = ["a", "b"] as const;\n`);
    expect(literal.join("\n")).not.toContain("FR-005");
  }, 60_000);
});
