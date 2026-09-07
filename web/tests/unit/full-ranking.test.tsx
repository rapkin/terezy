import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FullRanking } from "@/answer/components/FullRanking";
import { arrival, comparison, outcome, stayed } from "../answer-fixtures";
import { money, source } from "../fixtures";
import { day } from "@/design/format";

/**
 * FR-012: every ranked row with all five terms, the benchmark marked in **text**, tie groups as
 * groups.
 *
 * `benchmark`, `beats_benchmark` and `ties` are indices into `ranked`, so this renders the API's
 * own ordering and its own grouping; nothing here sorts and nothing here decides what ties.
 */
const RANKED = [outcome({ instrumentId: "A" }), outcome({ instrumentId: "B" }), outcome({ instrumentId: "C" })];

describe("the full ranking", () => {
  it("marks the benchmark row in text, not only in style", () => {
    const { container } = render(
      <FullRanking comparison={comparison({ ranked: RANKED, benchmark: 1 })} />,
    );
    const row = container.querySelector("[data-benchmark-row]");
    expect(row?.getAttribute("data-ranked-at")).toBe("1");
    expect(row?.querySelector("[data-benchmark-text]")?.textContent).toContain("the benchmark");
  });

  it("shows a tie group of two as one group", () => {
    const { container } = render(
      <FullRanking comparison={comparison({ ranked: RANKED, ties: [[0, 2]] })} />,
    );
    expect(container.querySelectorAll("[data-tie-group='0']")).toHaveLength(2);
  });

  it("says which rows beat the benchmark, in the API's own list", () => {
    const { container } = render(
      <FullRanking comparison={comparison({ ranked: RANKED, benchmark: 1, beats: [0] })} />,
    );
    expect(container.querySelectorAll("[data-beats-benchmark]")).toHaveLength(1);
  });

  it("carries all five terms on every row", () => {
    const { container } = render(<FullRanking comparison={comparison({ ranked: RANKED })} />);
    const rows = container.querySelectorAll("[data-ranked-at]");
    expect(rows).toHaveLength(3);
    for (const row of rows) {
      const named = [...row.querySelectorAll("[data-term]")].map((held) =>
        held.getAttribute("data-term"),
      );
      expect(named).toEqual(["instrument", "funded from", "route in", "exit terms", "route out"]);
    }
  });

  it("reads all-money-back the way the card does, and refuses where the card refuses", () => {
    // `span.end` and the last arrival agree on all 69 shipped rows, which is the condition under
    // which two readings of one question ship unnoticed. Both slots go through
    // `AllMoneyBackFigure`, so a remainder that stayed refuses in the ranking too.
    const stranded = outcome({
      instrumentId: "S",
      arrivals: [arrival("2026-10-04")],
      undeployed: {
        tag: "tuple.UndeployedCash",
        amount: money(494.68, [source()]),
        venue_id: "ibkr_usd",
        reason: "the purchase buys whole units only",
        journey: stayed("no declared way out carries it home"),
      },
    });
    const { container } = render(<FullRanking comparison={comparison({ ranked: [stranded] })} />);
    const row = container.querySelector("[data-ranked-at='0']");
    expect(row?.querySelector("[data-refusal='all money back on']")).not.toBeNull();
    expect(row?.textContent).toContain("no declared way out carries it home");
    expect(row?.textContent).toContain(day("2026-10-04"));
  });

  it("renders every row the API sent, and no row it did not", () => {
    const { container } = render(<FullRanking comparison={comparison({ ranked: RANKED })} />);
    expect(container.querySelector("summary")?.textContent).toContain("3");
    expect(container.querySelectorAll("[data-ranked-at]")).toHaveLength(RANKED.length);
  });
});
