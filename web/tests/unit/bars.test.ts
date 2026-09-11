import { describe, expect, it } from "vitest";
import { barsOf } from "@/card/bars";
import { cameHome, outcome, part } from "../answer-fixtures";
import { money, source } from "../fixtures";
import {
  charge,
  components,
  flow,
  notStated,
  projection,
  release,
  remainderWayOut,
  usd,
} from "../card-fixtures";

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

  it("draws one tax bar per flow, so both zeros reach the card", () => {
    // E11. Per **charge** the card could only ever draw the cited zero: a charge is struck by a
    // rule and cites it. The other zero — a line no rule ran on — is on the purchase flow, and
    // it reaches the screen only because the bars are built from the flows.
    const bars = barsOf(projection(), HELD).filter((bar) => bar.tag === "tax");
    expect(bars).toHaveLength(projection().flows.length);

    const charged = bars.find((bar) => bar.id === "tax:2");
    expect(charged?.amount.amount).toBe(0);
    expect(charged?.amount.provenance.sources.length).toBeGreaterThan(0);
    expect(charged?.base?.amount).toBe(500);
    expect(charged?.taxClassId).toBe("ua_government_bond");

    const unruled = bars.find((bar) => bar.id === "tax:1");
    expect(unruled?.amount.amount).toBe(0);
    expect(unruled?.amount.provenance.sources).toEqual([]);
    expect(unruled?.base).toBeNull();
    expect(unruled?.taxClassId).toBeNull();
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

  it("charges the remainder's own leg, on the date it left", () => {
    const left = outcome({
      instrumentId: "UA4000231195",
      undeployed: {
        tag: "tuple.UndeployedCash",
        amount: money(17.5, [source()]),
        venue_id: "inzhur",
        journey: cameHome("2026-09-05"),
        reason: "bought in whole increments",
      },
    });
    const bars = barsOf(projection({ remainder_way_out: remainderWayOut() }), left);
    const charged = bars.filter((bar) => bar.id.endsWith(":2026-09-01"));
    expect(charged).toHaveLength(3);
    expect(charged.every((bar) => bar.label.includes("could not deploy"))).toBe(true);
  });

  it("charges it nothing where it never travelled", () => {
    const bars = barsOf(projection(), HELD);
    expect(bars.some((bar) => bar.label.includes("could not deploy"))).toBe(false);
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
    // With parts on the outcome, or the check cannot fail however `barsOf` behaves. They are an
    // attribution in up to three currencies and two of them describe the same money from two
    // sides, so a bar built from one would double-count (FR-014).
    const attributed = outcome({
      instrumentId: "UA4000231195",
      parts: [part("entry", money(123.45, [source()])), part("ramp_in", money(67.89, [source()]))],
    });
    expect(attributed.parts).toHaveLength(2);
    const drawn = barsOf(projection(), attributed);
    expect(drawn.some((bar) => bar.id.startsWith("part"))).toBe(false);
    for (const bar of drawn) {
      if (bar.tag === "refused" || bar.tag === "none") continue;
      expect(bar.amount.amount).not.toBe(123.45);
      expect(bar.amount.amount).not.toBe(67.89);
    }
  });

  it("keeps a bar in another currency as that currency, converting nothing", () => {
    const held = projection({
      way_in: { ...projection().way_in, one_way: { ...projection().way_in.one_way, arrived: usd(1200) } },
    });
    const bar = barsOf(held, HELD).find((one) => one.id === "arrived");
    expect(bar?.tag === "amount" ? bar.amount.currency : null).toBe("USD");
  });

  it("sits each tax bar on the date of the flow it was struck on", () => {
    const bars = barsOf(projection(), HELD).filter((bar) => bar.tag === "tax");
    expect(bars.find((bar) => bar.id === "tax:2")?.on).toBe("2026-10-01");
    expect(bars.find((bar) => bar.id === "tax:1")?.on).toBe("2026-09-02");
    expect(charge().event_sequence).toBe(2);
  });
});
