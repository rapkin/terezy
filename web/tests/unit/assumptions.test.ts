import { describe, expect, it } from "vitest";
import { beyondShared, separatingFor, sharedAcross } from "@/answer/assumptions";
import { outcome, tuple } from "../answer-fixtures";

/**
 * FR-020, and plan Finding 4: the split is already computed and is not recomputed here.
 *
 * A set difference over served strings, never a similarity judgement.
 */
const EVERYWHERE = "the plan's own choices, the consumption method and the coupon policy";
const ALSO_EVERYWHERE = "the declared continuation assumption is 'hold_as_cash'";

describe("the shared assumptions", () => {
  const first = [EVERYWHERE, ALSO_EVERYWHERE, "only the first member rests on this"];
  const second = [EVERYWHERE, ALSO_EVERYWHERE, "only the second does"];

  it("is what every member rests on, in the first member's order", () => {
    expect(sharedAcross([first, second])).toEqual([EVERYWHERE, ALSO_EVERYWHERE]);
  });

  it("is empty where the members share nothing", () => {
    expect(sharedAcross([["a"], ["b"]])).toEqual([]);
  });

  it("is empty where there are no members, rather than everything", () => {
    expect(sharedAcross([])).toEqual([]);
  });

  it("leaves a member's own lines to the member, and none of them is shared", () => {
    const shared = sharedAcross([first, second]);
    const own = beyondShared(outcome({ instrumentId: "A", restsOn: first }), shared);
    expect(own).toEqual(["only the first member rests on this"]);
    for (const sentence of shared) expect(own).not.toContain(sentence);
  });
});

describe("what 019 says separates one member", () => {
  const separating = {
    tag: "dominance.SeparatingAssumptions" as const,
    per_member: [
      { tag: "dominance.MemberRestsOn" as const, key: tuple("A"), rests_on: ["A's own"], excludes: [] },
      { tag: "dominance.MemberRestsOn" as const, key: tuple("B"), rests_on: [], excludes: [] },
    ],
  };

  it("is found by key equality", () => {
    expect(separatingFor(tuple("A"), separating)?.rests_on).toEqual(["A's own"]);
  });

  it("is an empty list, not a missing member, for the one that rests on nothing extra", () => {
    expect(separatingFor(tuple("B"), separating)?.rests_on).toEqual([]);
  });

  it("is nothing where the pass stated that no assumption separates them", () => {
    const none = { tag: "dominance.NoStatedAssumptionSeparatesThem" as const };
    expect(separatingFor(tuple("A"), none)).toBeUndefined();
  });
});
