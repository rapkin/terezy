import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { groupNoCandidates } from "@/answer/grouping";
import { RefusalGroup } from "@/answer/components/RefusalGroup";
import { noCandidate } from "../answer-fixtures";

/**
 * FR-023: one line carrying the group's typed reason, expandable to each member — never a count
 * alone, and never a blank.
 */
const ROWS = Array.from({ length: 26 }, (_, at) => noCandidate(`UA400020${String(at)}`));

describe("a refusal group", () => {
  const [group] = groupNoCandidates(ROWS);

  it("collapses to one line carrying its typed reason and its count", () => {
    if (group === undefined) throw new Error("the fixture produced no group");
    const { container } = render(
      <RefusalGroup group={group} render={(member) => <span>{member.instrument_id}</span>} />,
    );
    const summary = container.querySelector("summary");
    expect(summary?.textContent).toContain("candidates.NothingConnects");
    expect(summary?.textContent).toContain("route_in");
    expect(summary?.textContent).toContain("contract_usd");
    expect(summary?.textContent).toContain("26");
  });

  it("expands to every member the count counted", () => {
    if (group === undefined) throw new Error("the fixture produced no group");
    const { container } = render(
      <RefusalGroup group={group} render={(member) => <span>{member.instrument_id}</span>} />,
    );
    const members = container.querySelectorAll("[data-group-members] > li");
    expect(members).toHaveLength(26);
    expect(members[0]?.textContent).toBe("UA4000200");
  });

  it("is never a count with nothing behind it", () => {
    if (group === undefined) throw new Error("the fixture produced no group");
    const { container } = render(
      <RefusalGroup group={group} render={(member) => <span>{member.why.reason}</span>} />,
    );
    for (const item of container.querySelectorAll("[data-group-members] > li")) {
      expect((item.textContent ?? "").trim()).not.toBe("");
    }
  });
});
