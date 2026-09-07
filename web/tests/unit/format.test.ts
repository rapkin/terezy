import { describe, expect, it } from "vitest";
import { GROUP, count, currencySymbol, day, money, quantity, rate } from "@/design/format";
import { money as moneyFixture, source } from "../fixtures";

/**
 * FR-026, and the web half of `cli-renders-raw-floats`.
 *
 * The two figures in that entry are the cases: an amount that arrived as
 * `49834.350000000006` and a rate that arrived as `3.7e-16`. Both are asserted here on the
 * formatter; that none reaches the rendered page is asserted end to end (SC-003).
 */
const THIN = GROUP;

describe("money", () => {
  it("states the kopeck and groups the thousands with a thin space", () => {
    expect(money(moneyFixture(62978.98287671233, [source()]))).toBe(`62${THIN}978.98${THIN}₴`);
  });

  it("renders the float that reached the CLI as a figure a reader can read", () => {
    expect(money(moneyFixture(49834.350000000006, [source()]))).toBe(`49${THIN}834.35${THIN}₴`);
  });

  it("groups every three digits, however many there are", () => {
    expect(money(moneyFixture(1234567.5, [source()]))).toBe(`1${THIN}234${THIN}567.50${THIN}₴`);
    expect(money(moneyFixture(7, [source()]))).toBe(`7.00${THIN}₴`);
  });

  it("keeps a negative amount negative", () => {
    expect(money(moneyFixture(-1200.5, [source()]))).toBe(`-1${THIN}200.50${THIN}₴`);
  });

  it("renders the currency the API returned it in, and converts nothing", () => {
    const dollars = { ...moneyFixture(1, [source()]), currency: "USD" } as const;
    expect(money(dollars)).toBe(`1.00${THIN}$`);
    expect(money(dollars)).not.toContain("₴");
    expect(currencySymbol("UAH")).toBe("₴");
  });
});

describe("a rate", () => {
  it("is a percent to two decimals", () => {
    expect(rate({ tag: "rates.NominalRate", value: 0.18112850290026622 })).toBe(`18.11${THIN}%`);
  });

  it("renders the exponent that reached the CLI as a percent, not as notation", () => {
    expect(rate({ tag: "rates.NominalRate", value: 3.7e-16 })).toBe(`0.00${THIN}%`);
  });

  it("keeps a negative rate negative", () => {
    expect(rate({ tag: "rates.NominalRate", value: -0.0325 })).toBe(`-3.25${THIN}%`);
  });
});

describe("a date", () => {
  it("renders an ISO date as 4 Oct 2026", () => {
    expect(day("2026-10-04")).toBe("4 Oct 2026");
    expect(day("2027-01-31")).toBe("31 Jan 2027");
  });

  it("returns a string that is not an ISO date unchanged, never a plausible wrong day", () => {
    expect(day("2026-13-01")).toBe("2026-13-01");
    expect(day("not a date")).toBe("not a date");
  });
});

describe("a quantity", () => {
  it("keeps a fraction a count would have truncated to zero", () => {
    expect(quantity(0.04)).toBe("0.04");
    expect(count(0.04)).toBe("0");
  });

  it("trims trailing zeros rather than claiming eight decimals of precision", () => {
    expect(quantity(2)).toBe("2");
    expect(quantity(1.5)).toBe("1.5");
    expect(quantity(12345.678)).toBe(`12${THIN}345.678`);
  });

  it("drops the float artefact without inventing a figure", () => {
    expect(quantity(0.1 + 0.2)).toBe("0.3");
  });

  it("states a bound rather than zero for a value finer than the last place", () => {
    expect(quantity(1e-12)).toBe("< 0.00000001");
    expect(quantity(0)).toBe("0");
  });

  it("keeps a negative quantity negative", () => {
    expect(quantity(-0.04)).toBe("-0.04");
  });
});

describe("a count", () => {
  it("is whole and grouped", () => {
    expect(count(26)).toBe("26");
    expect(count(12345)).toBe(`12${THIN}345`);
  });
});
