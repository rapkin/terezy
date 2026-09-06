import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { beliefsAcross } from "@/answer/beliefs";
import { SharedAssumptions } from "@/answer/components/SharedAssumptions";
import { SOLD_EARLY, outcome } from "../answer-fixtures";

/**
 * FR-024: once per screen **per distinct belief id**.
 *
 * Per id rather than once, because plan risk R2 is that a future registry produces members that
 * differ on the belief they carry — at which point the line becomes two lines rather than a
 * badge on every card.
 */
const CLEAN_PRICE = SOLD_EARLY.assumption;
const ANOTHER = { ...CLEAN_PRICE, id: "the_nav_is_struck_daily", rationale: "a second belief" };

describe("the belief line", () => {
  it("renders one line where two members lean on one belief", () => {
    const beliefs = beliefsAcross([
      outcome({ instrumentId: "A", quotation: CLEAN_PRICE }),
      outcome({ instrumentId: "B", quotation: CLEAN_PRICE }),
    ]);
    const { container } = render(<SharedAssumptions shared={[]} beliefs={beliefs} />);
    expect(container.querySelectorAll(`[data-belief='${CLEAN_PRICE.id}']`)).toHaveLength(1);
  });

  it("renders two where two distinct ids are on the screen", () => {
    const beliefs = beliefsAcross([
      outcome({ instrumentId: "A", quotation: CLEAN_PRICE }),
      outcome({ instrumentId: "B", quotation: ANOTHER }),
    ]);
    expect(beliefs.map((held) => held.id)).toEqual([CLEAN_PRICE.id, ANOTHER.id]);
    const { container } = render(<SharedAssumptions shared={[]} beliefs={beliefs} />);
    expect(container.querySelectorAll("[data-belief]")).toHaveLength(2);
  });

  it("reads the belief a sale was struck under as well as the one an outcome carried", () => {
    const beliefs = beliefsAcross([outcome({ instrumentId: "A", soldEarly: SOLD_EARLY })]);
    expect(beliefs.map((held) => held.id)).toEqual([CLEAN_PRICE.id]);
  });

  it("keeps the full statement reachable rather than eliding it", () => {
    const { container } = render(<SharedAssumptions shared={[]} beliefs={[CLEAN_PRICE]} />);
    expect(container.textContent).toContain(CLEAN_PRICE.rationale);
  });

  it("states once that a rate is measured on the money actually invested", () => {
    const { container } = render(<SharedAssumptions shared={["a"]} beliefs={[]} />);
    expect(container.querySelectorAll("[data-rate-scope]")).toHaveLength(1);
    expect(container.querySelector("[data-rate-scope]")?.textContent).toContain(
      "money actually invested",
    );
  });

  it("says so plainly where the members share nothing, rather than rendering an empty list", () => {
    const { container } = render(<SharedAssumptions shared={[]} beliefs={[]} />);
    expect(container.querySelector("[data-shared-none]")?.textContent).toContain("nothing is shared");
  });
});
