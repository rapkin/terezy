import { describe, expect, it } from "vitest";
import { taxZero } from "@/card/zeros";
import { money, source } from "../fixtures";
import { citedZero, uncitedZero } from "../card-fixtures";

/** Required test **E11**: the two zeros, from the shipped registry's own two cases. */
describe("which zero a tax of 0.00 is", () => {
  it("calls a zero carrying its exemption's citation exempted", () => {
    const held = taxZero(citedZero());
    expect(held.tag).toBe("exempted");
    expect(held.tag === "exempted" ? held.sources.length : 0).toBeGreaterThan(0);
  });

  it("calls a zero resting on no source at all one no rule ran on", () => {
    expect(taxZero(uncitedZero()).tag).toBe("no-rule-ran");
  });

  it("calls a figure that is not zero charged, whatever it cites", () => {
    expect(taxZero(money(3876.84, [source()])).tag).toBe("charged");
    expect(taxZero(money(3876.84, [])).tag).toBe("charged");
  });

  it("discriminates on the citation and never on the amount alone", () => {
    // The mutation: strip the exemption's source and the same 0.00 becomes the other claim.
    expect(taxZero(citedZero()).tag).not.toBe(taxZero(uncitedZero()).tag);
    expect(citedZero().amount).toBe(uncitedZero().amount);
  });
});
