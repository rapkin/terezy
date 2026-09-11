import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Timeline } from "@/card/components/Timeline";
import { cameHome, outcome, stayed } from "../answer-fixtures";
import { money, source } from "../fixtures";
import { cashArm, flow, projection } from "../card-fixtures";

const HELD = outcome({ instrumentId: "UA4000231195" });

function withRemainder(journey: ReturnType<typeof cameHome>) {
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
  it("draws the window's two boundaries and every served event", () => {
    const { container } = render(<Timeline projection={projection()} outcome={HELD} />);
    expect(container.querySelector("[data-event-kind='window-start']")).not.toBeNull();
    expect(container.querySelector("[data-event-kind='window-end']")).not.toBeNull();
    expect(container.querySelector("[data-event='purchase']")).not.toBeNull();
    expect(container.querySelectorAll("[data-event-kind='arrival']")).toHaveLength(1);
  });

  it("marks an event outside the window in text rather than dropping or clamping it", () => {
    const { container } = render(
      <Timeline
        projection={projection({ flows: [flow({ sequence: 2, occurred_on: "2027-06-01" })] })}
        outcome={HELD}
      />,
    );
    const late = container.querySelector("[data-event='flow:2']");
    expect(late?.getAttribute("data-outside")).toBe("yes");
    expect(late?.textContent).toContain("outside the horizon window");
  });

  it("states each latency in the declared days the API sent", () => {
    const { container } = render(<Timeline projection={projection()} outcome={HELD} />);
    const segments = [...container.querySelectorAll("[data-segment]")].map(
      (held) => held.textContent ?? "",
    );
    expect(segments[0]).toContain("1 day(s) of waiting");
    expect(segments[1]).toContain("3 day(s) of waiting");
  });

  it("gives the remainder its own marker where it came home", () => {
    const { container } = render(
      <Timeline projection={projection()} outcome={withRemainder(cameHome("2026-09-05"))} />,
    );
    expect(container.querySelector("[data-event-kind='remainder-arrival']")).not.toBeNull();
    expect(container.querySelector("[data-remainder-mark='came-home']")).not.toBeNull();
  });

  it("names the state where it did not, and draws no marker for it", () => {
    const { container } = render(
      <Timeline projection={projection()} outcome={withRemainder(stayed("the way out refuses"))} />,
    );
    expect(container.querySelector("[data-event-kind='remainder-arrival']")).toBeNull();
    expect(container.querySelector("[data-remainder-mark='stayed']")?.textContent).toContain(
      "the way out refuses",
    );
  });

  it("names the dated records an arm states none of", () => {
    const { container } = render(
      <Timeline projection={projection({ arm: cashArm() })} outcome={HELD} />,
    );
    const absences = [...container.querySelectorAll("[data-not-stated]")];
    expect(absences.length).toBeGreaterThan(0);
    for (const absence of absences) expect(absence.textContent).not.toBe("");
  });

  it("reads as text with every style declaration stripped", () => {
    const { container } = render(<Timeline projection={projection()} outcome={HELD} />);
    for (const element of container.querySelectorAll("[class],[style]")) {
      element.removeAttribute("class");
      element.removeAttribute("style");
    }
    const text = container.textContent ?? "";
    expect(text).toContain("the horizon opens");
    expect(text).toContain("the purchase settles");
    expect(text).toContain("reaches a spendable endpoint");
  });
});
