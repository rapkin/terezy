import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Waterfall } from "@/card/components/Waterfall";
import { GROUP } from "@/design/format";
import { outcome } from "../answer-fixtures";
import { money, source } from "../fixtures";
import { fundArm, projection, usd } from "../card-fixtures";

const HELD = outcome({ instrumentId: "UA4000231195" });

function draw(over: Parameters<typeof projection>[0] = {}, held = HELD) {
  return render(<Waterfall projection={projection(over)} outcome={held} />);
}

describe("the waterfall", () => {
  it("draws the bars in the order the money moved", () => {
    const { container } = draw();
    const kinds = [...container.querySelectorAll("[data-bar-kind]")].map((held) =>
      held.getAttribute("data-bar-kind"),
    );
    expect(kinds[0]).toBe("outlay");
    expect(kinds[kinds.length - 1]).toBe("home");
    expect(kinds.indexOf("purchase")).toBeLessThan(kinds.indexOf("released"));
    expect(kinds.indexOf("released")).toBeLessThan(kinds.indexOf("tax"));
    expect(kinds.indexOf("tax")).toBeLessThan(kinds.indexOf("way-out"));
  });

  it("states that the bars do not add up to the rate, and why", () => {
    const { container } = draw();
    const said = container.querySelector("[data-does-not-sum]")?.textContent ?? "";
    expect(said).toContain("do not add up");
    expect(said).toContain("percentage exit fee");
  });

  it("draws a bar the arm states no flow for as a refusal, never a zero", () => {
    const { container } = draw({ arm: fundArm() });
    const premium = container.querySelector("[data-bar='premium']");
    expect(premium?.querySelector("[data-figure='refused']")).not.toBeNull();
    expect(premium?.textContent).not.toContain(`0.00${GROUP}₴`);
  });

  it("gives every bar with an amount a mark, and never an unmarked value slot", () => {
    const { container } = draw();
    expect(container.querySelectorAll("[data-figure='value']")).toHaveLength(0);
    for (const slot of container.querySelectorAll("[data-figure='marked']")) {
      expect(slot.querySelectorAll("[data-mark]").length).toBeGreaterThan(0);
    }
  });

  it("says whose mark a bar wears when the amount itself cites nothing", () => {
    const bare = projection();
    const { container } = render(
      <Waterfall
        projection={{
          ...bare,
          way_in: {
            ...bare.way_in,
            one_way: { ...bare.way_in.one_way, arrived: money(1, []) },
          },
        }}
        outcome={HELD}
      />,
    );
    expect(container.querySelector("[data-mark-owner='outcome']")).not.toBeNull();
  });

  it("draws no joined baseline where the bars are in two currencies, and consults no rate", () => {
    const bare = projection();
    const { container } = render(
      <Waterfall
        projection={{
          ...bare,
          way_in: { ...bare.way_in, one_way: { ...bare.way_in.one_way, arrived: usd(1200) } },
        }}
        outcome={HELD}
      />,
    );
    expect(container.querySelector("[data-currencies-split]")).not.toBeNull();
    expect(container.querySelectorAll("[data-currency-group]")).toHaveLength(2);
    expect(container.querySelector("[data-split-reason]")?.textContent).toContain(
      "no rate is consulted",
    );
  });

  it("reads as text with every style declaration stripped", () => {
    const { container } = draw();
    for (const element of container.querySelectorAll("[class],[style]")) {
      element.removeAttribute("class");
      element.removeAttribute("style");
    }
    const text = container.textContent ?? "";
    expect(text).toContain("left the income stream");
    expect(text).toContain("reached a spendable endpoint");
    expect(text).toContain(`50${GROUP}000.00`);
  });

  it("lets no unrounded float reach the document", () => {
    const { container } = draw(
      {},
      outcome({ instrumentId: "A", reaches: money(50529.090769230774, [source()]) }),
    );
    expect(container.textContent).not.toContain("50529.090769230774");
    expect(container.textContent).toContain(`50${GROUP}529.09`);
  });
});
