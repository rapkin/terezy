import { describe, expect, it } from "vitest";
import { isMoney, isProvenance, isRefusal, isStalenessVerdict } from "@/lib/provenance";
import { isListing, isRecordRead, isRegistry, isSeriesListing, isSeriesWindow } from "@/lib/narrow";
import { instrumentRead, keyedSummary, money, provenance, registry, source, verdict } from "../fixtures";

describe("the guards test what their renderers read", () => {
  it("accepts the shapes the API sends", () => {
    expect(isProvenance(provenance([source()]))).toBe(true);
    expect(isMoney(money(1, [source()]))).toBe(true);
    expect(isStalenessVerdict(verdict([]))).toBe(true);
    expect(isRegistry(registry([keyedSummary()]))).toBe(true);
    expect(isRecordRead(instrumentRead())).toBe(true);
  });

  it("refuses a body missing a field its renderer reads", () => {
    expect(isProvenance({ tag: "provenance.Provenance", sources: [] })).toBe(false);
    expect(isMoney({ tag: "money.Money", amount: 1, currency: "UAH" })).toBe(false);
    expect(isRecordRead({ ...instrumentRead(), fields: [{ tag: "nope" }] })).toBe(false);
    expect(isRegistry({ ...registry([]), categories: [{ tag: "summary.KeyedSummary" }] })).toBe(false);
  });

  it("refuses a body whose tag is not the one the renderer expects", () => {
    expect(isListing(instrumentRead())).toBe(false);
    expect(isSeriesWindow(instrumentRead())).toBe(false);
    expect(isRefusal(provenance([source()]))).toBe(false);
  });

  it("a listing is a series listing only where the API states coverage", () => {
    const plain = {
      tag: "envelopes.ListingOfInstruments",
      category: "instruments",
      as_of: "2026-09-05",
      scenario_id: null,
      ids: ["UA1"],
    };
    expect(isListing(plain)).toBe(true);
    expect(isSeriesListing(plain)).toBe(false);
    expect(isSeriesListing({ ...plain, coverage: {} })).toBe(true);
  });

  it("recognises every refusal the document declares, and nothing that merely carries a reason", () => {
    expect(
      isRefusal({
        tag: "envelopes.WindowMalformed",
        series_id: "x",
        asked: ["a", "b"],
        reason: "a window is two-ended.",
      }),
    ).toBe(true);
    expect(
      isRefusal({ tag: "envelopes.OnlyTheEndsChecked", reason: "only the ends were compared." }),
    ).toBe(false);
  });
});
