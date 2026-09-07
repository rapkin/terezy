import { describe, expect, it } from "vitest";
import { joinToOutcome, placeable } from "@/answer/join";
import { sameTuple } from "@/answer/keys";
import { comparison, outcome, tuple } from "../answer-fixtures";

/**
 * FR-009 and FR-010: the key-equality join, and the named state where it finds nothing.
 *
 * The unmatched arm cannot arise on the shipped registry and is not assumed away — a card built
 * from `undefined` would render five empty slots rather than say that the answer disagrees with
 * itself.
 */
describe("joining a non-dominated key to its ranked outcome", () => {
  const ranked = [outcome({ instrumentId: "A" }), outcome({ instrumentId: "B" })];

  it("finds the member whose whole key matches", () => {
    const joined = joinToOutcome(tuple("B"), ranked);
    expect(joined.tag).toBe("joined");
    expect(joined.tag === "joined" && joined.outcome.key.instrument_id).toBe("B");
  });

  it("returns the named state carrying the key where nothing matches", () => {
    const key = tuple("NOBODY");
    expect(joinToOutcome(key, ranked)).toEqual({ tag: "no-ranked-outcome", key });
  });

  it("matches on the whole tuple and not on the instrument alone", () => {
    expect(joinToOutcome(tuple("A", "contract_usd"), ranked).tag).toBe("no-ranked-outcome");
  });

  it("searches what the pass placed, which is the ranked rows and the not-comparable ones", () => {
    // `dominance.py::_population` is `evaluated(comparison)`. A row whose rate refused is a
    // complete outcome and can be non-dominated — the objectives are money and date, not the
    // rate — so a join over `ranked` alone renders "on the front and in no ranked row" against
    // a member the API placed.
    const unrated = outcome({
      instrumentId: "UNRATED",
      rate: {
        tag: "tuple.RateNotComparable",
        missing: "a rate over a span this short",
        reason: "an annualised rate over no time is not a rate.",
      },
    });
    const held = comparison({ ranked, notComparable: [unrated] });
    expect(placeable(held).map((one) => one.key.instrument_id)).toEqual(["A", "B", "UNRATED"]);
    expect(joinToOutcome(tuple("UNRATED"), placeable(held)).tag).toBe("joined");
    expect(joinToOutcome(tuple("UNRATED"), held.ranked).tag).toBe("no-ranked-outcome");
  });

  it("compares keys structurally, so a field added to one side stops it matching", () => {
    const held = tuple("A");
    expect(sameTuple(held, tuple("A"))).toBe(true);
    expect(sameTuple(held, { ...held, stream_id: "contract_usd" })).toBe(false);
    expect(
      sameTuple(held, { ...held, route_out: { tag: "path.ComposedExit", segments: ["a", "b"] } }),
    ).toBe(false);
  });
});
