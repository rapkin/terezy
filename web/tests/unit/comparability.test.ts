import { describe, expect, it } from "vitest";
import { spanDays, spansDiffer } from "@/answer/comparability";
import { range } from "../answer-fixtures";

/**
 * FR-014: the predicate yields a boolean and never a figure.
 *
 * The span *range* the CLI composes is OB-16 and belongs to the API; a second client composing
 * the same sentence is where two readers get two answers.
 */
describe("the comparability predicate", () => {
  it("is true where the shipped one-month front's two spans differ", () => {
    // 33 days and 18 days, measured 2026-09-06.
    expect(
      spansDiffer([range("2026-09-01", "2026-10-04"), range("2026-09-01", "2026-09-19")]),
    ).toBe(true);
  });

  it("is false where two rows of different dates were measured over the same length", () => {
    expect(
      spansDiffer([range("2026-09-01", "2026-10-01"), range("2026-10-01", "2026-10-31")]),
    ).toBe(false);
  });

  it("is false for one row and for none", () => {
    expect(spansDiffer([range("2026-09-01", "2026-10-04")])).toBe(false);
    expect(spansDiffer([])).toBe(false);
  });

  it("counts days across a month, a year and a leap day", () => {
    expect(spanDays(range("2026-09-01", "2026-10-04"))).toBe(33);
    expect(spanDays(range("2026-09-01", "2027-09-01"))).toBe(365);
    expect(spanDays(range("2024-02-28", "2024-03-01"))).toBe(2);
  });

  it("returns no length for a date it cannot read, and calls the section incomparable", () => {
    expect(spanDays(range("not a date", "2026-10-04"))).toBeNull();
    expect(spansDiffer([range("not a date", "x"), range("2026-09-01", "2026-10-04")])).toBe(true);
  });
});
