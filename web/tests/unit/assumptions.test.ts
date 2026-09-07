import { describe, expect, it } from "vitest";
import { beyondShared, separatingFor, sharedAcross, sharedFor } from "@/answer/assumptions";
import { outcome, tuple } from "../answer-fixtures";

/**
 * FR-020, and plan Finding 4: the split is already computed and is not recomputed here.
 *
 * A set difference over served strings, never a similarity judgement.
 */
const EVERYWHERE = "the plan's own choices, the consumption method and the coupon policy";
const ALSO_EVERYWHERE = "the declared continuation assumption is 'hold_as_cash'";

const SEPARATING = {
  tag: "dominance.SeparatingAssumptions" as const,
  per_member: [
    {
      tag: "dominance.MemberRestsOn" as const,
      key: tuple("A"),
      rests_on: ["only the first member rests on this"],
      excludes: [],
    },
    { tag: "dominance.MemberRestsOn" as const, key: tuple("B"), rests_on: [], excludes: [] },
  ],
};

const FIRST = outcome({
  instrumentId: "A",
  restsOn: [EVERYWHERE, ALSO_EVERYWHERE, "only the first member rests on this"],
});
const SECOND = outcome({ instrumentId: "B", restsOn: [EVERYWHERE, ALSO_EVERYWHERE] });

describe("the shared assumptions", () => {
  it("is a member's rests_on less what 019 said separates it", () => {
    expect(sharedFor(FIRST, SEPARATING)).toEqual([EVERYWHERE, ALSO_EVERYWHERE]);
  });

  it("is the same for every member of a section, which is what makes it one line", () => {
    // Measured 2026-09-07 across all three shipped fronts: two sentences, identical for every
    // member. The member 019 named nothing for is the one that would break it if the split were
    // recomputed from the members instead of read off the pass.
    expect(sharedFor(SECOND, SEPARATING)).toEqual(sharedFor(FIRST, SEPARATING));
  });

  it("folds to what every shown member shares, in the first member's order", () => {
    const perMember = [FIRST, SECOND].map((held) => sharedFor(held, SEPARATING));
    expect(sharedAcross(perMember)).toEqual([EVERYWHERE, ALSO_EVERYWHERE]);
  });

  it("is empty where the members share nothing, and where there are none", () => {
    expect(sharedAcross([["a"], ["b"]])).toEqual([]);
    expect(sharedAcross([])).toEqual([]);
  });

  it("leaves a member's own lines to the member, and none of them is shared", () => {
    const shared = sharedAcross([FIRST, SECOND].map((held) => sharedFor(held, SEPARATING)));
    const own = beyondShared(FIRST, shared);
    expect(own).toEqual(["only the first member rests on this"]);
    for (const sentence of shared) expect(own).not.toContain(sentence);
  });
});

describe("what 019 says separates one member", () => {
  it("is found by key equality", () => {
    expect(separatingFor(tuple("A"), SEPARATING)?.rests_on).toEqual([
      "only the first member rests on this",
    ]);
  });

  it("is an empty list, not a missing member, for the one that rests on nothing extra", () => {
    expect(separatingFor(tuple("B"), SEPARATING)?.rests_on).toEqual([]);
  });

  it("leaves everything shared where the pass stated that no assumption separates them", () => {
    const none = { tag: "dominance.NoStatedAssumptionSeparatesThem" as const };
    expect(separatingFor(tuple("A"), none)).toBeUndefined();
    expect(sharedFor(FIRST, none)).toEqual(FIRST.rests_on);
  });
});
