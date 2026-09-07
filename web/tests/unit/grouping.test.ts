import { describe, expect, it } from "vitest";
import { groupNoCandidates, groupRefusals } from "@/answer/grouping";
import { noCandidate, refusedTuple } from "../answer-fixtures";

/**
 * FR-022, over the population it was measured on: 27 rows sharing `(NothingConnects, route_in,
 * contract_usd)` and differing only in the instrument id inside each reason's own sentence.
 */
const MEASURED = Array.from({ length: 27 }, (_, at) => noCandidate(`UA400020${String(at)}`));

describe("grouping the no-candidate pairs", () => {
  it("collapses the measured population to one group holding all 27", () => {
    const groups = groupNoCandidates(MEASURED);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.members).toHaveLength(27);
  });

  it("keeps every id it counted reachable", () => {
    const groups = groupNoCandidates(MEASURED);
    const reachable = groups.flatMap((group) => group.members.map((held) => held.instrument_id));
    expect(reachable.sort()).toEqual(MEASURED.map((held) => held.instrument_id).sort());
  });

  it("groups on the typed fields and not on the reason text", () => {
    const same = [
      noCandidate("A"),
      { ...noCandidate("B"), why: { ...noCandidate("B").why, reason: "a different sentence" } },
    ];
    expect(groupNoCandidates(same)).toHaveLength(1);
  });

  it("separates two sides and two streams", () => {
    const groups = groupNoCandidates([
      noCandidate("A"),
      noCandidate("B", { side: "route_out" }),
      noCandidate("C", { streamId: "salary_uah" }),
    ]);
    expect(groups).toHaveLength(3);
  });
});

describe("grouping the refused tuples", () => {
  it("folds four refusals of one tag into one line", () => {
    const groups = groupRefusals([
      refusedTuple("A", "one reason"),
      refusedTuple("B", "another reason entirely"),
      refusedTuple("C", "a third"),
      refusedTuple("D", "a fourth"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.on).toEqual([{ field: "refusal", value: "tuple.InstrumentRefused" }]);
    expect(groups[0]?.members).toHaveLength(4);
  });
});
