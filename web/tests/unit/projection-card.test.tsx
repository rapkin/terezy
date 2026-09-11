import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CandidateCard } from "@/card/components/CandidateCard";
import { GROUP } from "@/design/format";
import { outcome } from "../answer-fixtures";
import { money, source } from "../fixtures";
import { projection } from "../card-fixtures";

const MARKED = outcome({
  instrumentId: "UA4000231195",
  reaches: money(50529.090769230774, [source({ verified_on: null })]),
});

function card() {
  return render(<CandidateCard projection={projection()} outcome={MARKED} />);
}

describe("the candidate card", () => {
  it("carries the waterfall, the attribution and the timeline, each labelled", () => {
    const { container } = card();
    expect(container.querySelector("[data-waterfall]")).not.toBeNull();
    expect(container.querySelector("[data-timeline]")).not.toBeNull();
    expect(container.querySelector("[data-disclosure='attribution']")).not.toBeNull();
  });

  it("folds the attribution and leaves the waterfall open", () => {
    const { container } = card();
    const folded = container.querySelector("[data-disclosure='attribution']");
    expect(folded?.hasAttribute("open")).toBe(false);
    expect(container.querySelector("[data-waterfall] [data-bar='outlay']")).not.toBeNull();
  });

  it("warns that the attribution is not an addition", () => {
    const { container } = card();
    expect(container.querySelector("[data-attribution-warning]")?.textContent).toContain(
      "double-counts",
    );
  });

  it("puts the full provenance behind one disclosure, reachable and never elided", () => {
    const { container } = card();
    const held = container.querySelector("[data-disclosure='provenance']");
    expect(held).not.toBeNull();
    const listed = [...(held?.querySelectorAll("[data-source]") ?? [])];
    expect(listed.length).toBeGreaterThan(0);
    for (const entry of listed) expect(entry.textContent).toContain("retrieved");
  });

  it("names the belief it leans on and does not restate it", () => {
    const held = outcome({
      instrumentId: "A",
      quotation: {
        tag: "quotation.QuotationHolds",
        id: "the_clean_price_holds",
        rationale: "the observed spread holds",
        is_assumption: true,
      },
    });
    const { container } = render(<CandidateCard projection={projection()} outcome={held} />);
    expect(container.querySelector("[data-belief-mark='the_clean_price_holds']")).not.toBeNull();
    expect(container.textContent).not.toContain("the observed spread holds");
  });

  it("lets no unrounded float reach the document", () => {
    const { container } = card();
    expect(container.textContent).not.toContain("50529.090769230774");
    expect(container.textContent).toContain(`50${GROUP}529.09`);
  });

  it("renders no figure as an unmarked value", () => {
    const { container } = card();
    expect(container.querySelectorAll("[data-figure='value']")).toHaveLength(0);
  });
});
