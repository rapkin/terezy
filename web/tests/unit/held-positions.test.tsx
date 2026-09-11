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

  it("is one disclosure whatever its lots number, and the population counts positions", () => {
    // The owner holds his BTC in two lots. A second lot drawn as a population of its own put a
    // second disclosure inside the position and its members inside the held population, where
    // the count-matches-members guard read them as the population's own.
    const lot = HELD.lots[0];
    if (lot === undefined) throw new Error("the fixture declares no lot");
    const two = {
      ...HELD,
      quantity: 0.3,
      lots: [lot, { ...lot, lot_id: "btc-2", quantity: 0.2, acquired_on: "2025-06-02" }],
    };
    const { container } = render(<HeldPositions held={[two]} staleness={verdict([])} />);
    const population = container.querySelector("[data-population='what the owner already holds']");
    expect(population?.getAttribute("data-count")).toBe("1");
    const position = container.querySelector("[data-held='btc']");
    expect(position?.querySelectorAll("details")).toHaveLength(1);
    expect(position?.querySelectorAll("[data-lot]")).toHaveLength(2);
    expect(container.querySelectorAll("[data-population]")).toHaveLength(1);
  });

  it("routes every quantity through the formatting module, position and lot alike", () => {
    // A holding is summed from its lots in float64, so it arrives carrying the artefact —
    // 0.1 + 0.2 is 0.30000000000000004 — and that is what `String(n)` would put on the screen.
    const lot = HELD.lots[0];
    if (lot === undefined) throw new Error("the fixture declares no lot");
    const summed = {
      ...HELD,
      quantity: 0.1 + 0.2,
      lots: [
        { ...lot, quantity: 0.1 },
        { ...lot, lot_id: "btc-2", quantity: 0.2 },
      ],
    };
    const { container } = render(<HeldPositions held={[summed]} staleness={verdict([])} />);
    const marked = [...container.querySelectorAll("[data-quantity]")].map(
      (held) => held.textContent,
    );
    expect(marked).toEqual(["0.3", "0.1", "0.2"]);
  });
});
