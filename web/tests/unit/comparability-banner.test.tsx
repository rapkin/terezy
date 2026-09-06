import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ComparabilityBanner } from "@/answer/components/ComparabilityBanner";
import { spansDiffer } from "@/answer/comparability";
import { range } from "../answer-fixtures";

/**
 * SC-007's negative half is a unit assertion and not an end-to-end one: measured 2026-09-06 all
 * three shipped sections have rows of differing span, so an end-to-end negative would pass by
 * asserting nothing.
 */
describe("the comparability banner", () => {
  it("states the condition and its consequence, and composes no span range", () => {
    const { container } = render(<ComparabilityBanner />);
    const text = container.textContent ?? "";
    expect(text).toContain("different length");
    expect(text).toContain("annualised over its own span");
    // The span range is OB-16 and belongs to the API. Nothing here composes one.
    expect(text).not.toMatch(/\d/);
  });

  it("is shown for mixed spans and absent for equal ones", () => {
    expect(spansDiffer([range("2026-09-01", "2026-10-04"), range("2026-09-01", "2026-09-19")])).toBe(
      true,
    );
    expect(spansDiffer([range("2026-09-01", "2026-10-01"), range("2026-11-01", "2026-12-01")])).toBe(
      false,
    );
  });
});
