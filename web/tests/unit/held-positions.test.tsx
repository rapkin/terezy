import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { HeldPositions } from "@/answer/components/HeldPositions";
import { money as rendered, plain } from "@/design/format";
import { money, source, verdict } from "../fixtures";
import { HELD } from "../answer-fixtures";

/**
 * What the owner already holds, drawn beside what he could do with the amount he asked about.
 *
 * A held position is `NotRankedAgainstTheBenchmark` by 025's own verdict, so it is never a card
 * on a front — and its valuation is the figure most likely to be missing, because it needs a
 * price observation the registry may not have on the date asked.
 */
const PAIR: ["USD", "UAH"] = ["USD", "UAH"];

describe("a held position", () => {
  it("states what it cost and what it is worth, each wearing its own marks", () => {
    const { container } = render(<HeldPositions held={[HELD]} staleness={verdict([])} />);
    const held = container.querySelector("[data-held='btc']");
    expect(held?.textContent).toContain(rendered(HELD.basis));
    expect(held?.textContent).toContain("0.04 BTC at binance");
    expect(container.querySelectorAll("[data-figure='value']")).toHaveLength(0);
    expect(container.textContent).toContain("unverified");
  });

  it("leads with the base-currency figure the engine computed, not the price-currency one", () => {
    // The basis is in the base currency. Showing the value struck in the price currency beside
    // it read as a 97% loss where the engine had computed a 32% gain.
    const valued = HELD.valuation;
    if (valued.tag !== "held.Valued" || valued.in_base.tag !== "held.InBaseCurrency") {
      throw new Error("the fixture is not a valued position in the base currency");
    }
    const { container } = render(<HeldPositions held={[HELD]} staleness={verdict([])} />);
    const held = container.querySelector("[data-held='btc']");
    expect(held?.textContent).toContain(rendered(valued.in_base.value));
    expect(held?.textContent).toContain(rendered(valued.in_base.nominal_change));
    // And the price-currency figure is still there, said to be in its own currency.
    expect(held?.textContent).toContain(rendered(valued.value));
    expect(held?.textContent).toContain("struck in its own currency");
  });

  it("states the close and the date it was observed", () => {
    const { container } = render(<HeldPositions held={[HELD]} staleness={verdict([])} />);
    const quoted = container.querySelector("[data-quotation]");
    expect(quoted?.getAttribute("data-quotation")).toBe("2026-09-05");
    expect(quoted?.textContent).toContain(plain(78000));
  });

  it("marks the peg the dollar figure rests on, rather than dropping it", () => {
    // 025 declares `QuoteAssetIsWorth` required-without-a-default so that a dollar figure
    // cannot rest on an unstated peg. A screen that renders the figure and not the belief has
    // dropped the mark the field exists to carry.
    const { container } = render(<HeldPositions held={[HELD]} staleness={verdict([])} />);
    expect(container.querySelector("[data-belief-mark='usdt_is_a_dollar']")).not.toBeNull();
  });

  it("renders a base-currency restatement the rate could not strike as its own reason", () => {
    const valued = HELD.valuation;
    if (valued.tag !== "held.Valued") throw new Error("the fixture is not valued");
    const unstruck = {
      ...HELD,
      valuation: {
        ...valued,
        in_base: {
          tag: "official_rate.OfficialRateUndeclaredOnDate" as const,
          series_id: "ua_nbu_usd",
          pair: PAIR,
          on_date: "2026-09-05",
          covers: null,
          reason: "no official rate is declared for 2026-09-05.",
        },
      },
    };
    const { container } = render(<HeldPositions held={[unstruck]} staleness={verdict([])} />);
    expect(
      container.querySelector("[data-refusal='official_rate.OfficialRateUndeclaredOnDate']")
        ?.textContent,
    ).toContain("no official rate is declared");
    expect(container.querySelector("[data-held='btc']")?.textContent).toContain(
      rendered(valued.value),
    );
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
