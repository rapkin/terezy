import { describe, expect, it } from "vitest";
import { positionOf, remainderOf, timelineOf } from "@/card/events";
import { cameHome, outcome, range, stayed } from "../answer-fixtures";
import { money, source } from "../fixtures";
import {
  distribution,
  flow,
  fundArm,
  projection,
  release,
  remainderWayOut,
} from "../card-fixtures";

const HELD = outcome({ instrumentId: "UA4000231195" });

function remainder(journey: ReturnType<typeof cameHome>) {
  return outcome({
    instrumentId: "UA4000231195",
    undeployed: {
      tag: "tuple.UndeployedCash",
      amount: money(17.5, [source()]),
      venue_id: "inzhur",
      journey,
      reason: "bought in whole increments",
    },
  });
}

describe("the timeline", () => {
  it("draws the window's two boundaries and places every event by its served date", () => {
    const held = timelineOf(projection(), HELD);
    expect(held.window).toEqual({ start: HELD.horizon.start, end: HELD.horizon.end });
    expect(held.events.map((event) => event.kind)).toContain("window-start");
    expect(held.events.map((event) => event.kind)).toContain("window-end");
    expect(held.events.map((event) => event.on)).toEqual(
      [...held.events].map((event) => event.on).sort(),
    );
  });

  it("draws an event outside the window outside it and marked, never dropped", () => {
    const held = timelineOf(
      projection({ flows: [flow({ sequence: 2, occurred_on: "2027-06-01" })] }),
      HELD,
    );
    const late = held.events.find((event) => event.on === "2027-06-01");
    expect(late?.outside).toBe(true);
    expect(positionOf("2027-06-01", held.window)).toBeGreaterThan(1);
  });

  it("keeps a date whose payment its own tax consumed exactly", () => {
    // The released series drops such a date and the schedule does not — which is the coupon a
    // reader most needs, because the ledger says it happened and nothing came home from it.
    const consumed = projection({
      flows: [
        flow({
          sequence: 2,
          occurred_on: "2026-09-20",
          gross: money(500, [source()]),
          tax: money(500, [source()]),
          net: money(0, [source()]),
        }),
      ],
      releases: [],
    });
    const held = timelineOf(consumed, HELD);
    expect(held.events.some((event) => event.on === "2026-09-20")).toBe(true);
    expect(held.events.some((event) => event.kind === "arrival")).toBe(false);
  });

  it("takes a latency segment's length from the served declared days, in and out", () => {
    const held = timelineOf(projection(), HELD);
    expect(held.segments.map((segment) => segment.days)).toEqual([1, 3]);
    expect(held.segments[1]).toMatchObject({ from: "2026-10-01", to: "2026-10-04" });
  });

  it("draws one out segment per release rather than one per flow", () => {
    const held = timelineOf(
      projection({
        flows: [flow({ sequence: 2 }), flow({ sequence: 3, kind: "redemption" })],
        releases: [release()],
      }),
      HELD,
    );
    expect(held.segments.filter((segment) => segment.id.startsWith("latency:out"))).toHaveLength(1);
  });

  it("gives the remainder its own arrival where the engine says it came home", () => {
    const held = timelineOf(projection(), remainder(cameHome("2026-09-05")));
    expect(held.remainder).toEqual({ tag: "came-home", on: "2026-09-05" });
    expect(held.events.some((event) => event.kind === "remainder-arrival")).toBe(true);
  });

  it("draws the remainder's own wait from the charge served for its leg", () => {
    // Its arrival had a marker and no segment beside it: the remainder leaves on the purchase
    // date with no position behind it, so it is on none of the dated releases.
    const served = projection({ remainder_way_out: remainderWayOut() });
    const held = timelineOf(served, remainder(cameHome("2026-09-05")));
    const segment = held.segments.find((one) => one.id === "latency:out:remainder");
    expect(segment).toMatchObject({ from: "2026-09-01", to: "2026-09-05", days: 3 });
  });

  it("draws no such wait where the remainder never travelled", () => {
    const held = timelineOf(projection(), remainder(stayed("the way out refuses")));
    expect(held.segments.some((one) => one.id === "latency:out:remainder")).toBe(false);
  });

  it("gives it a named state and no marker where the engine says it did not", () => {
    const held = timelineOf(projection(), remainder(stayed("the way out will not carry it")));
    expect(held.remainder.tag).toBe("stayed");
    expect(held.events.some((event) => event.kind === "remainder-arrival")).toBe(false);
  });

  it("says nothing was left over where the outcome carries no remainder", () => {
    expect(remainderOf(HELD)).toEqual({ tag: "none" });
  });

  it("keeps both distributions where a fund declares two on one record date", () => {
    // The id was the record date alone, so the two collided and one marker left the timeline.
    const held = timelineOf(
      projection({
        arm: fundArm({
          distributions: [
            distribution({ record_on: "2027-01-10", paid_on: "2027-01-20" }),
            distribution({ record_on: "2027-01-10", paid_on: "2027-02-20" }),
          ],
        }),
      }),
      HELD,
    );
    const markers = held.events.filter((event) => event.id.startsWith("record-date:"));
    expect(markers).toHaveLength(2);
    expect(new Set(markers.map((event) => event.id)).size).toBe(2);
  });

  it("renders a flow kind it has no label for raw rather than blank", () => {
    const held = timelineOf(projection({ flows: [flow({ sequence: 2, kind: "fee" })] }), HELD);
    expect(held.events.find((event) => event.id === "flow:2")?.detail).toBe("fee");
  });

  it("places a date inside the window between its two ends", () => {
    const window = range("2026-09-01", "2026-10-01");
    expect(positionOf("2026-09-01", window)).toBe(0);
    expect(positionOf("2026-10-01", window)).toBe(1);
    expect(positionOf("2026-09-16", window)).toBeGreaterThan(0.4);
    expect(positionOf("2026-09-16", window)).toBeLessThan(0.6);
  });

  it("never clamps: an event before the window is placed before it", () => {
    expect(positionOf("2026-08-01", { start: "2026-09-01", end: "2026-10-01" })).toBeLessThan(0);
  });
});
