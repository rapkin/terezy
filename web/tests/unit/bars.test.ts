import { describe, expect, it } from "vitest";
import { barsOf } from "@/card/bars";
import { outcome, cameHome } from "../answer-fixtures";
import { money, source } from "../fixtures";
import { charge, components, flow, notStated, projection, release, usd } from "../card-fixtures";

/**
 * One case per row of the plan's mapping table: every bar's amount is a field the API sent, and
 * no bar is the difference between two others.
 */
const HELD = outcome({ instrumentId: "UA4000231195" });

function amountOf(id: string) {
  const bar = barsOf(projection(), HELD).find((held) => held.id === id);
  if (bar === undefined || bar.tag === "refused" || bar.tag === "none") {
    throw new Error(`no amount bar ${id}`);
  }
  return bar.amount.amount;
}

describe("the waterfall's bars", () => {
  it("opens with what left the income stream, which is the outcome's own outlay", () => {
    expect(amountOf("outlay")).toBe(HELD.outlay.amount);
  });

  it("draws one bar per component of the way in's charge and none for their total", () => {
    const bars = barsOf(projection(), HELD).filter((bar) => bar.kind === "way-in");
    expect(bars.map((bar) => bar.id)).toEqual([
      "way-in:conversion_spread:once",
      "way-in:percentage_fee:once",
      "way-in:fixed_fee:once",
    ]);
  });

  it("draws what arrived from the served arrived, not from the outlay less the components", () => {
    expect(amountOf("arrived")).toBe(49982.5);
  });

  it("draws the purchase total, the price per unit, and the split of that price", () => {
    // The split is struck on the quotation and is therefore **per unit**: 970.12 + 15.86 is
    // 985.98, the price, and not the 49 299.21 the purchase paid. Drawing it under the total
    // would report an accrual fifty times smaller than the one actually paid.
    expect(amountOf("purchase")).toBe(49299.21);
    expect(amountOf("price")).toBe(985.98);
    expect(amountOf("accrued:clean") + amountOf("accrued:accrued")).toBe(amountOf("price"));
  });

  it("says on the bars themselves that the split is per unit, and how many were bought", () => {
    const bars = barsOf(projection(), HELD);
    const labels = Object.fromEntries(bars.map((bar) => [bar.id, bar.label]));
    expect(labels["purchase"]).toContain("50 unit(s)");
    expect(labels["accrued:accrued"]).toContain("per unit");
    expect(labels["accrued:clean"]).toContain("per unit");
  });

  it("refuses the accrued bar where the arm carried no quotation", () => {
    const held = projection({
      purchase: { ...projection().purchase, carried: notStated("carried", "fund") },
    });
    const bar = barsOf(held, HELD).find((one) => one.id === "accrued");
    expect(bar?.tag).toBe("refused");
  });

  it("draws the remainder from the outcome's own record, and a named state where there is none", () => {
    // `undeployed: null` is the API saying the purchase deployed the whole of what arrived —
    // a fact, not an absence, so it is its own state rather than a refusal.
    const nothing = barsOf(projection(), HELD).find((bar) => bar.kind === "remainder");
    expect(nothing?.tag).toBe("none");
    const left = outcome({
      instrumentId: "UA4000231195",
      undeployed: {
        tag: "tuple.UndeployedCash",
        amount: money(17.5, [source()]),
        venue_id: "inzhur",
        journey: cameHome(),
        reason: "bought in whole increments",
      },
    });
    const bar = barsOf(projection(), left).find((held) => held.kind === "remainder");
    expect(bar?.tag === "amount" ? bar.amount.amount : null).toBe(17.5);
  });

  it("draws the holding's releases gross, and never the purchase among them", () => {
    const released = barsOf(projection(), HELD).filter((bar) => bar.kind === "released");
    expect(released).toHaveLength(1);
    expect(released[0]?.tag === "amount" ? released[0].amount.amount : null).toBe(500);
  });

  it("draws the tax from the charge's own total, with the base beside it", () => {
    const bar = barsOf(projection(), HELD).find((held) => held.kind === "tax");
    expect(bar?.tag).toBe("tax");
    if (bar?.tag !== "tax") throw new Error("no tax bar");
    expect(bar.amount.amount).toBe(0);
    expect(bar.base.amount).toBe(500);
    expect(bar.taxClassId).toBe("ua_government_bond");
  });

  it("draws the way out per dated release rather than per flow", () => {
    // Two flows on one date travel home once and share one charge: drawing one bar per flow
    // would report the flat fee twice.
    const held = projection({
      flows: [
        flow({ sequence: 2, kind: "coupon", occurred_on: "2026-10-01" }),
        flow({ sequence: 3, kind: "redemption", occurred_on: "2026-10-01" }),
      ],
      releases: [release()],
    });
    const exits = barsOf(held, HELD).filter((bar) => bar.kind === "way-out");
    expect(exits).toHaveLength(3);
    expect(exits.every((bar) => bar.id.endsWith(":2026-10-01"))).toBe(true);
  });

  it("closes with what reached home, which is `reaches` and not the sum of the bars", () => {
    const bars = barsOf(projection(), HELD);
    const last = bars[bars.length - 1];
    expect(last?.id).toBe("home");
    expect(last?.tag === "amount" ? last.amount.amount : null).toBe(HELD.reaches.amount);
  });

  it("yields the served amounts even where they cannot sum to what came back", () => {
    // The mutation the rule exists for: a fixture whose bars add up to something else entirely.
    // Every bar is still the served figure, because no bar is computed from another.
    const wrong = projection({
      way_in: { ...projection().way_in, one_way: { ...projection().way_in.one_way, arrived: money(1, [source()]) } },
    });
    expect(barsOf(wrong, HELD).find((bar) => bar.id === "arrived")).toMatchObject({
      amount: { amount: 1 },
    });
    expect(barsOf(wrong, HELD).find((bar) => bar.id === "home")).toMatchObject({
      amount: { amount: HELD.reaches.amount },
    });
  });

  it("labels a component the client has no words for with the term the API sent", () => {
    const held = projection({
      way_in: {
        ...projection().way_in,
        one_way: {
          ...projection().way_in.one_way,
          components: { ...components(), stamp_duty: money(3, [source()]) },
        },
      },
    });
    const labels = barsOf(held, HELD)
      .filter((bar) => bar.kind === "way-in")
      .map((bar) => bar.label);
    expect(labels[labels.length - 1]).toContain("stamp_duty");
  });

  it("reads no attribution: the six parts never reach a bar", () => {
    const withParts = outcome({ instrumentId: "UA4000231195" });
    expect(withParts.parts).toEqual([]);
    const ids = barsOf(projection(), withParts).map((bar) => bar.id);
    expect(ids.some((id) => id.startsWith("part"))).toBe(false);
  });

  it("keeps a bar in another currency as that currency, converting nothing", () => {
    const held = projection({
      way_in: { ...projection().way_in, one_way: { ...projection().way_in.one_way, arrived: usd(1200) } },
    });
    const bar = barsOf(held, HELD).find((one) => one.id === "arrived");
    expect(bar?.tag === "amount" ? bar.amount.currency : null).toBe("USD");
  });

  it("sits the charge bar on the date of the flow it was struck on", () => {
    const bar = barsOf(projection(), HELD).find((held) => held.kind === "tax");
    expect(bar?.tag === "tax" ? bar.on : null).toBe("2026-10-01");
    expect(charge().event_sequence).toBe(2);
  });
});
