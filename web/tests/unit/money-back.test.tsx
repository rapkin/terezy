import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { allMoneyBackOn } from "@/answer/all-money-back";
import { MoneyBack } from "@/answer/components/MoneyBack";
import { GROUP, day, money as rendered } from "@/design/format";
import { money, source } from "../fixtures";
import { arrival, cameHome, outcome, stayed } from "../answer-fixtures";

/**
 * FR-016 and FR-017: *money back* is one served figure, and the remainder is a disclosure with
 * the engine's own verdict on it rather than an operand.
 *
 * Measured 2026-09-06, before the engine fix, a one-month member reached 49 760.50 ₴ against
 * 50 000 ₴ asked while reporting +10.99 %, because `reaches` was measured on what was deployed
 * and the 494.68 ₴ remainder was a separate field nothing brought home.
 */
const REACHES = money(50529.090769230774, [source()]);
const REMAINDER = money(494.68120879120397, [source()]);

function remainder(journey: ReturnType<typeof cameHome>) {
  return {
    tag: "tuple.UndeployedCash" as const,
    amount: REMAINDER,
    venue_id: "inzhur",
    reason: "the purchase buys whole units only",
    journey,
  };
}

describe("money back", () => {
  it("is the served figure, with nothing added to it and no deployed part composed", () => {
    const { container } = render(
      <MoneyBack
        outcome={outcome({
          instrumentId: "UA4000235865",
          reaches: REACHES,
          undeployed: remainder(cameHome()),
        })}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain(rendered(REACHES));
    // The sum the client must not compose, and the difference it must not compose either.
    expect(text).not.toContain(`51${GROUP}023.77`);
    expect(text).not.toContain(`50${GROUP}034.41`);
  });

  it("carries the mark its provenance puts on it", () => {
    const { container } = render(
      <MoneyBack outcome={outcome({ instrumentId: "A", reaches: REACHES })} />,
    );
    expect(container.textContent).toContain("unverified");
  });

  it("shows the served remainder record beside it — amount, venue and constraint", () => {
    const { container } = render(
      <MoneyBack
        outcome={outcome({ instrumentId: "A", reaches: REACHES, undeployed: remainder(cameHome()) })}
      />,
    );
    const disclosure = container.querySelector("[data-disclosure='remainder']");
    expect(disclosure?.textContent).toContain(rendered(REMAINDER));
    expect(disclosure?.textContent).toContain("inzhur");
    expect(disclosure?.textContent).toContain("whole units only");
  });

  it("says the remainder came home, on the dates the record gives", () => {
    const { container } = render(
      <MoneyBack
        outcome={outcome({
          instrumentId: "A",
          reaches: REACHES,
          undeployed: remainder(cameHome("2026-10-04")),
        })}
      />,
    );
    const held = container.querySelector("[data-journey='came-home']");
    expect(held?.textContent).toContain(day("2026-10-04"));
    expect(held?.textContent).toContain("inside the figure above");
  });

  it("names the state where the served verdict says the remainder stayed", () => {
    const { container } = render(
      <MoneyBack
        outcome={outcome({
          instrumentId: "A",
          reaches: REACHES,
          undeployed: remainder(stayed("no declared way out carries USD home from ibkr_usd")),
        })}
      />,
    );
    // A headline that quietly stood for the whole amount is FR-016's measured defect again.
    const held = container.querySelector("[data-journey='stayed'] [data-missing]");
    expect(held?.textContent).toContain("no declared way out carries USD home");
    expect(container.querySelector("[data-all-money-back='not-all-of-it']")).not.toBeNull();
  });

  it("reads a null remainder as nothing left over, not as a missing field", () => {
    const { container } = render(
      <MoneyBack outcome={outcome({ instrumentId: "A", reaches: REACHES, undeployed: null })} />,
    );
    expect(container.querySelector("[data-remainder='none']")?.textContent).toBe(
      "nothing left over",
    );
    expect(container.querySelector("[data-missing]")).toBeNull();
  });
});

describe("all of it by", () => {
  it("is the last arrival, which is the figure the dominance pass reads", () => {
    const held = outcome({
      instrumentId: "A",
      arrivals: [arrival("2026-09-19"), arrival("2026-10-04")],
    });
    expect(allMoneyBackOn(held)).toEqual({ tag: "on", date: "2026-10-04" });
    const { container } = render(<MoneyBack outcome={held} />);
    expect(container.querySelector("[data-all-money-back='on']")?.textContent).toContain(
      day("2026-10-04"),
    );
  });

  it("is refused where a remainder the way out would not carry is still behind", () => {
    const held = outcome({
      instrumentId: "A",
      arrivals: [arrival("2026-10-04")],
      undeployed: remainder(stayed("the way out will not carry it")),
    });
    // The engine returns `FigureUnavailable` here, so a date on the card would be a figure the
    // ordering does not have.
    expect(allMoneyBackOn(held)).toEqual({
      tag: "not-all-of-it",
      mostOfItOn: "2026-10-04",
      reason: "the way out will not carry it",
    });
  });

  it("is refused where nothing arrived at all", () => {
    expect(allMoneyBackOn(outcome({ instrumentId: "A", arrivals: [] }))).toEqual({
      tag: "nothing-arrived",
    });
    const { container } = render(
      <MoneyBack outcome={outcome({ instrumentId: "A", arrivals: [] })} />,
    );
    expect(
      container.querySelector("[data-all-money-back='nothing-arrived']")?.textContent,
    ).toContain("no arrival at all");
  });
});
