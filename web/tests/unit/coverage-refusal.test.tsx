import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CoverageRefusal } from "@/components/series/CoverageRefusal";

describe("CoverageRefusal", () => {
  it("renders the refusal for the missing part with its reason (FR-029)", () => {
    const { container } = render(
      <CoverageRefusal
        outside={{
          tag: "envelopes.WindowOutsideCoverage",
          series_id: "ua_cpi_monthly",
          asked: ["2025-01", "2030-01"],
          covers: ["1991-08", "2025-10"],
          missing: ["2030-01"],
          reason: "the series declares no observation for 1 of the periods asked for.",
        }}
        checked={{ tag: "envelopes.EveryPeriodChecked" }}
      />,
    );
    expect(container.textContent).toContain("declares no observation for 1 of the periods");
    expect(container.querySelector("[data-checked='every']")).not.toBeNull();
  });

  it("says what was checked where only the window's ends were (OnlyTheEndsChecked)", () => {
    const reason =
      "an official-rate series declares no periodicity, so which dates between its first and its last were expected is not a fact this layer has.";
    const { container } = render(
      <CoverageRefusal outside={null} checked={{ tag: "envelopes.OnlyTheEndsChecked", reason }} />,
    );
    expect(container.querySelector("[data-checked='ends']")?.textContent).toBe(reason);
    expect(container.querySelector("[data-figure='refused']")).toBeNull();
  });

  it("says nothing was checked against a window where none was asked for", () => {
    const { container } = render(
      <CoverageRefusal outside={null} checked={{ tag: "envelopes.NoWindowAsked" }} />,
    );
    expect(container.querySelector("[data-checked='none']")?.textContent).toContain(
      "no window was asked for",
    );
  });
});
