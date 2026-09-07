import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { HeldPositions } from "@/answer/components/HeldPositions";
import { money as rendered } from "@/design/format";
import { money, source, verdict } from "../fixtures";
import { HELD } from "../answer-fixtures";

/**
 * What the owner already holds, drawn beside what he could do with the amount he asked about.
 *
 * A held position is `NotRankedAgainstTheBenchmark` by 025's own verdict, so it is never a card
 * on a front — and its valuation is the figure most likely to be missing, because it needs a
 * price observation the registry may not have on the date asked.
 */
describe("a held position", () => {
  it("states what it cost and what it is worth, each wearing its own marks", () => {
    const { container } = render(<HeldPositions held={[HELD]} staleness={verdict([])} />);
    const held = container.querySelector("[data-held='btc']");
    expect(held?.textContent).toContain(rendered(HELD.basis));
    expect(held?.textContent).toContain("0.04 BTC at binance");
    expect(container.querySelectorAll("[data-figure='value']")).toHaveLength(0);
    expect(container.textContent).toContain("unverified");
  });

  it("renders a valuation the registry could not strike as its reason, never as a blank", () => {
    const unpriced = {
      ...HELD,
      valuation: {
        tag: "quotations.NoQuotationOnDate" as const,
        symbol: "BTCUSDT",
        on_date: "2026-09-05",
        covers: null,
        reason: "no price observation covers 2026-09-05 for btc.",
      },
    };
    const { container } = render(<HeldPositions held={[unpriced]} staleness={verdict([])} />);
    const refused = container.querySelector("[data-refusal='quotations.NoQuotationOnDate']");
    expect(refused?.textContent).toContain("no price observation covers");
    expect(container.querySelector("[data-held='btc']")?.textContent).toContain(
      rendered(HELD.basis),
    );
  });

  it("says it is not ranked against the benchmark, in the engine's own words", () => {
    const { container } = render(<HeldPositions held={[HELD]} staleness={verdict([])} />);
    const rank = container.querySelector("[data-typed-state='held.NotRankedAgainstTheBenchmark']");
    expect(rank?.textContent).toContain("money not yet spent");
  });

  it("renders nothing misleading where the owner holds nothing", () => {
    const { container } = render(<HeldPositions held={[]} staleness={verdict([])} />);
    const population = container.querySelector("[data-population]");
    expect(population?.getAttribute("data-count")).toBe("0");
    expect(population?.textContent).toContain("none");
    expect(container.querySelectorAll("[data-held]")).toHaveLength(0);
  });

  it("carries the lots behind a disclosure rather than on the line", () => {
    const { container } = render(
      <HeldPositions
        held={[{ ...HELD, basis: money(96000, [source()]) }]}
        staleness={verdict([])}
      />,
    );
    expect(container.querySelector("[data-lot='btc-1']")?.textContent).toContain("2025-03-11");
  });
});
