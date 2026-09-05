import { describe, expect, it } from "vitest";
import { parseAsOf, parseWindow, stringOrUndefined } from "@/search/params";

describe("as_of", () => {
  it("accepts a calendar date", () => {
    expect(parseAsOf("2026-09-05")).toEqual({ tag: "given", value: "2026-09-05" });
  });

  it("names the parameter on an invalid value and substitutes no default (FR-020)", () => {
    const parsed = parseAsOf("yesterday");
    expect(parsed.tag).toBe("invalid");
    if (parsed.tag !== "invalid") throw new Error("expected an invalid parse");
    expect(parsed.parameter).toBe("as_of");
    expect(parsed.given).toBe("yesterday");
    expect(Object.values(parsed)).not.toContain("2026-09-05");
  });

  it("reports a missing value as missing rather than as today", () => {
    expect(parseAsOf(undefined)).toEqual({ tag: "missing", parameter: "as_of" });
  });

  it("reports an as_of written and left blank as invalid, not as absent", () => {
    // Absent redirects with the clock read; blank is a value the reader gave, and reading it as
    // absent left a page with no figure, no error and no control to recover from.
    expect(parseAsOf("").tag).toBe("invalid");
  });

  it("refuses a value the router's parser coerced out of a string (FR-020)", () => {
    // `?as_of=20260905` reaches validateSearch as a number, and mapping it to `undefined` would
    // make it indistinguishable from absent -- so the route would redirect with today's date.
    expect(parseAsOf(stringOrUndefined(20260905)).tag).toBe("invalid");
    expect(parseAsOf(stringOrUndefined(true)).tag).toBe("invalid");
    expect(parseAsOf(stringOrUndefined(["2026-09-05"])).tag).toBe("invalid");
    expect(stringOrUndefined(undefined)).toBeUndefined();
    expect(stringOrUndefined("2026-09-05")).toBe("2026-09-05");
  });

  it("refuses a date-shaped string that is not a date", () => {
    expect(parseAsOf("2026-13-45").tag).toBe("invalid");
  });
});

describe("the series window", () => {
  it("accepts two dates and two periods", () => {
    expect(parseWindow("2019-12-28", "2026-08-31").tag).toBe("given");
    expect(parseWindow("1991-08", "2025-10").tag).toBe("given");
  });

  it("refuses one end alone, naming the parameter (FR-027)", () => {
    const parsed = parseWindow("2019-12-28", undefined);
    expect(parsed.tag).toBe("invalid");
    if (parsed.tag !== "invalid") throw new Error("expected an invalid parse");
    expect(parsed.parameter).toBe("from,to");
    expect(parsed.reason).toContain("two-ended");
  });

  it("refuses a window that ends before it begins", () => {
    const parsed = parseWindow("2026-01-01", "2025-01-01");
    expect(parsed.tag).toBe("invalid");
  });

  it("reports both ends absent as missing, so the route can ask the API for coverage", () => {
    expect(parseWindow(undefined, undefined)).toEqual({ tag: "missing", parameter: "from,to" });
  });

  it("refuses a window whose ends the router's parser coerced, rather than replacing it", () => {
    expect(parseWindow(stringOrUndefined(2026), stringOrUndefined(2027)).tag).toBe("invalid");
    expect(parseWindow("", "").tag).toBe("invalid");
  });
});
