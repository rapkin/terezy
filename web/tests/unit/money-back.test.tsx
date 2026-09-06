import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MoneyBack } from "@/answer/components/MoneyBack";
import { GROUP, money as rendered } from "@/design/format";
import { money, source } from "../fixtures";
import { outcome } from "../answer-fixtures";

/**
 * FR-016 and FR-017: *money back* is one served figure, and the remainder is a disclosure rather
 * than an operand.
 *
 * Measured 2026-09-06, before the engine fix, a one-month member reached 49 760.50 ₴ against
 * 50 000 ₴ asked while reporting +10.99 %, because `reaches` was measured on what was deployed
 * and the 494.68 ₴ remainder was a separate field nothing brought home.
 */
const REACHES = money(49760.5, [source()]);
const REMAINDER = money(494.68120879120397, [source()]);

describe("money back", () => {
  it("is the served figure, with nothing added to it", () => {
    const { container } = render(
      <MoneyBack
        outcome={outcome({
          instrumentId: "UA4000235865",
          reaches: REACHES,
          undeployed: {
            tag: "tuple.UndeployedCash",
            amount: REMAINDER,
            venue_id: "inzhur",
            reason: "the purchase buys whole units only",
          },
        })}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain(rendered(REACHES));
    // The sum the client must not compose, and the difference it must not compose either.
    expect(text).not.toContain(`50${GROUP}255.18`);
    expect(text).not.toContain(`49${GROUP}265.82`);
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
        outcome={outcome({
          instrumentId: "A",
          reaches: REACHES,
          undeployed: {
            tag: "tuple.UndeployedCash",
            amount: REMAINDER,
            venue_id: "inzhur",
            reason: "the purchase buys whole units only",
          },
        })}
      />,
    );
    const disclosure = container.querySelector("[data-disclosure='remainder']");
    expect(disclosure).not.toBeNull();
    expect(disclosure?.textContent).toContain(rendered(REMAINDER));
    expect(disclosure?.textContent).toContain("inzhur");
    expect(disclosure?.textContent).toContain("whole units only");
  });

  it("names the state where the remainder is in a currency the headline is not in", () => {
    const { container } = render(
      <MoneyBack
        outcome={outcome({
          instrumentId: "A",
          reaches: REACHES,
          undeployed: {
            tag: "tuple.UndeployedCash",
            amount: { ...REMAINDER, currency: "USD" },
            venue_id: "ibkr_usd",
            reason: "the purchase buys whole units only",
          },
        })}
      />,
    );
    // No rate is consulted anywhere on this screen, so the headline cannot stand for the whole
    // amount and must say so.
    const named = container.querySelector("[data-missing]");
    expect(named).not.toBeNull();
    expect(named?.textContent).toContain("USD");
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
