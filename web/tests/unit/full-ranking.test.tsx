import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FullRanking } from "@/answer/components/FullRanking";
import { comparison, outcome } from "../answer-fixtures";

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

  it("renders every row the API sent, and no row it did not", () => {
    const { container } = render(<FullRanking comparison={comparison({ ranked: RANKED })} />);
    expect(container.querySelector("summary")?.textContent).toContain("3");
    expect(container.querySelectorAll("[data-ranked-at]")).toHaveLength(RANKED.length);
  });
});
