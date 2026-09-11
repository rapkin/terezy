import { describe, expect, it } from "vitest";
import { barsOf } from "@/card/bars";
import { isAbsence, remedyFor } from "@/card/refusals";
import { outcome } from "../answer-fixtures";
import { fundArm, notStated, projection } from "../card-fixtures";

const HELD = outcome({ instrumentId: "UA4000231195" });

describe("the named states this card can be in", () => {
  it("gives the two endpoint refusals different remedies, because they are different faults", () => {
    const wrongUrl = remedyFor({
      tag: "envelopes.CategoryHasNoSuchId",
      category: "questions",
      wanted_id: "nope",
      declared_ids: ["fifty-thousand-hryvnia"],
      reason: "no question with that id is declared",
    });
    const staleClient = remedyFor({
      tag: "card.NoSuchCandidate",
      wanted_key: "nope",
      evaluated_keys: ["a", "b"],
      reason: "no candidate of this answer is addressed by that",
    });
    expect(wrongUrl).not.toBe(staleClient);
    expect(wrongUrl).toContain("question");
    expect(staleClient).toContain("answer");
  });

  it("calls a record the arm does not state an absence, and a zero not one", () => {
    expect(isAbsence(notStated("exit_line"))).toBe(true);
    expect(isAbsence({ tag: "money.Money", amount: 0 })).toBe(false);
    expect(isAbsence(null)).toBe(false);
  });

  it("draws a bar an arm states no flow for as a refusal carrying its reason", () => {
    const held = projection({ arm: fundArm() });
    const bars = barsOf(held, HELD);
    const refused = bars.filter((bar) => bar.tag === "refused");
    expect(refused.length).toBeGreaterThan(0);
    for (const bar of refused) {
      expect(bar.state.reason).toBeTruthy();
      expect(bar.state.what).toBeTruthy();
      expect(bar).not.toHaveProperty("amount");
    }
  });
});
