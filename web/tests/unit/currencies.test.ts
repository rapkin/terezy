import { describe, expect, it } from "vitest";
import { barsOf } from "@/card/bars";
import { currenciesOf, inCurrency, sharesOneCurrency } from "@/card/currencies";
import { outcome } from "../answer-fixtures";
import { projection, usd } from "../card-fixtures";

const HELD = outcome({ instrumentId: "UA4000231195" });

/** FR-015: a boolean and a list of tags. No figure and no rate in the return type. */
describe("whether one connected waterfall is drawable", () => {
  it("says yes where every bar is in one currency", () => {
    const bars = barsOf(projection(), HELD);
    expect(sharesOneCurrency(bars)).toBe(true);
    expect(currenciesOf(bars)).toEqual(["UAH"]);
  });

  it("says no where the way in arrived in another", () => {
    const held = projection({
      way_in: { ...projection().way_in, one_way: { ...projection().way_in.one_way, arrived: usd(1200) } },
    });
    const bars = barsOf(held, HELD);
    expect(sharesOneCurrency(bars)).toBe(false);
    expect(currenciesOf(bars)).toEqual(["UAH", "USD"]);
  });

  it("groups per currency and keeps every refusal in each group", () => {
    const held = projection({
      way_in: { ...projection().way_in, one_way: { ...projection().way_in.one_way, arrived: usd(1200) } },
    });
    const bars = barsOf(held, HELD);
    const dollars = inCurrency(bars, "USD");
    expect(dollars.some((bar) => bar.id === "arrived")).toBe(true);
    expect(dollars.some((bar) => bar.id === "home")).toBe(false);
    // A bar with no amount belongs to no currency, so it stays in every group rather than
    // disappearing from the one a reader happens to open.
    expect(dollars.some((bar) => bar.tag === "none" || bar.tag === "refused")).toBe(true);
  });

  it("consults no rate: the return types carry neither a figure nor one", () => {
    const bars = barsOf(projection(), HELD);
    expect(typeof sharesOneCurrency(bars)).toBe("boolean");
    expect(currenciesOf(bars).every((held) => typeof held === "string")).toBe(true);
  });
});
