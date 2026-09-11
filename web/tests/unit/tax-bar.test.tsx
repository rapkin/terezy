import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { TaxBar } from "@/card/components/TaxBar";
import { money, source } from "../fixtures";
import { citedZero, uncitedZero } from "../card-fixtures";

/** Required test **E11**: the two zeros render differently, and neither is blank. */
function bar(amount: Parameters<typeof TaxBar>[0]["amount"]) {
  return render(
    <TaxBar
      amount={amount}
      base={money(500, [source()])}
      taxClassId="ua_government_bond"
      on="2026-10-01"
    />,
  );
}

describe("the tax bar", () => {
  it("says a cited zero is an exemption and names the provision", () => {
    const { container } = bar(citedZero());
    expect(container.querySelector("[data-tax-zero='exempted']")).not.toBeNull();
    expect(container.querySelector("[data-zero='exempted']")?.textContent).toContain(
      "tax/ua.toml#ua_government_bond",
    );
  });

  it("says an uncited zero is a line no rule ran on", () => {
    const { container } = bar(uncitedZero());
    expect(container.querySelector("[data-tax-zero='no-rule-ran']")).not.toBeNull();
    expect(container.querySelector("[data-zero='no-rule-ran']")?.textContent).toContain(
      "rests on no source",
    );
  });

  it("renders the two zeros differently, and neither blank", () => {
    const exempt = bar(citedZero()).container.textContent ?? "";
    const unruled = bar(uncitedZero()).container.textContent ?? "";
    expect(exempt).not.toBe(unruled);
    expect(exempt.trim()).not.toBe("");
    expect(unruled.trim()).not.toBe("");
  });

  it("puts the base beside the charge and names the class", () => {
    const { container } = bar(money(3876.84, [source()]));
    expect(container.textContent).toContain("struck on");
    expect(container.querySelector("[data-tax-class]")?.textContent).toBe("ua_government_bond");
    expect(container.querySelector("[data-tax-zero='charged']")).not.toBeNull();
  });

  it("shows no rate: the engine records none and this client derives none", () => {
    const { container } = bar(money(3876.84, [source()]));
    expect(container.textContent).not.toMatch(/\d\s*%/);
  });
});
