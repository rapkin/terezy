import { describe, expect, it } from "vitest";
import { separatingBadge } from "@/answer/separating";
import { SOLD_EARLY, outcome, range, servedOutcome } from "../answer-fixtures";

/**
 * FR-019, one case per row of plan Finding 2's table.
 *
 * The third case is the one that would have been missed: the member sold at the window's end
 * carries **no** separating sentence, because what separates it is the *absence* of the
 * continuation assumption its neighbour has. A badge read off `per_member[].rests_on` would be
 * blank on exactly the member that most needs one.
 */
describe("the separating badge", () => {
  it("says sold at the end where the outcome carries a sale", () => {
    const badge = separatingBadge(outcome({ instrumentId: "UA4000239016", soldEarly: SOLD_EARLY }));
    expect(badge).toEqual({ tag: "sold-at-the-end", on: SOLD_EARLY.on });
  });

  it("says the sold-early member's own thing even though it rests on no sentence", () => {
    // The member whose `separating.per_member[].rests_on` is empty, measured 2026-09-06.
    const sold = outcome({ instrumentId: "UA4000239016", soldEarly: SOLD_EARLY, restsOn: [] });
    expect(separatingBadge(sold).tag).toBe("sold-at-the-end");
  });

  it("says its own terms closed it where the outcome carries no sale", () => {
    const badge = separatingBadge(
      outcome({ instrumentId: "UA4000235865", span: range("2026-09-01", "2026-09-19") }),
    );
    expect(badge).toEqual({ tag: "closed-by-its-own-terms" });
  });

  it("does not read the span against the horizon", () => {
    // Two members whose spans end either side of the horizon, both with no sale: the badge is
    // the same, because `span` is first outlay to last arrival and reading it as the exit date
    // would have inverted the two members plan Finding 2 measured.
    const inside = outcome({ instrumentId: "A", span: range("2026-09-01", "2026-09-19") });
    const beyond = outcome({ instrumentId: "B", span: range("2026-09-01", "2027-07-24") });
    expect(separatingBadge(inside)).toEqual(separatingBadge(beyond));
  });

  it("renders a sale tag it has no label for raw, never blank", () => {
    const widened = servedOutcome({
      ...outcome({ instrumentId: "C", soldEarly: SOLD_EARLY }),
      sold_early: { ...SOLD_EARLY, tag: "early_exit.SoldByAMechanismNobodyNamed" },
    });
    expect(separatingBadge(widened)).toEqual({
      tag: "unlabelled",
      raw: "early_exit.SoldByAMechanismNobodyNamed",
    });
  });
});
