import { describe, expect, it } from "vitest";
import { assertNever } from "@/lib/exhaustive";
import type { Refusal } from "@/api/shapes";

type Two = { tag: "a" } | { tag: "b" };

function handled(value: Two): string {
  switch (value.tag) {
    case "a":
      return "a";
    case "b":
      return "b";
  }
  assertNever(value);
}

function unhandled(value: Two): string {
  // The missing arm is what this fixture is for: the rule firing here is the rule working.
  // eslint-disable-next-line @typescript-eslint/switch-exhaustiveness-check
  switch (value.tag) {
    case "a":
      return "a";
  }
  // @ts-expect-error FR-004: a member no case handles is a compile error at the site that
  // does not handle it. This line goes red the day that stops being true.
  assertNever(value);
}

describe("assertNever", () => {
  it("is the arm a handled union never reaches", () => {
    expect(handled({ tag: "a" })).toBe("a");
    expect(handled({ tag: "b" })).toBe("b");
  });

  it("throws where a body arrives that the type it was generated from forbids", () => {
    expect(() => unhandled({ tag: "b" })).toThrow(/unhandled member/);
  });

  it("the refusal union is derived from the document, not listed", () => {
    // Every tag below comes out of `Refusal`, so this array cannot be written for a member the
    // document does not declare -- and a member it gains is one this list does not have.
    const tags: Refusal["tag"][] = [
      "envelopes.CategoryHasNoSuchId",
      "envelopes.FileNotRecorded",
      "envelopes.NothingDeclared",
      "envelopes.ScenarioNotDeclared",
      "envelopes.WindowMalformed",
      "envelopes.WindowOutsideCoverage",
      "middleware.HostNotDeclared",
      "middleware.NotOnLoopback",
      "service.PathNotServed",
    ];
    expect(new Set(tags).size).toBe(tags.length);
  });
});
